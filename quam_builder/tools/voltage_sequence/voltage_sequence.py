from typing import Dict, Optional, Tuple

import numpy as np
from qm.qua import (
    declare,
    assign,
    fixed,
    Cast,
    ramp,
    ramp_to_zero,
    Math,
    if_,
    else_,
)
from qm.qua.type_hints import (
    QuaVariable,
    QuaScalarExpression,
)

from quam.components.channels import SingleChannel

from quam_builder.architecture.quantum_dots.components.gate_set import (
    GateSet,
    VoltageTuningPoint,
)
import warnings
from .sequence_state_tracker import SequenceStateTracker
from .exceptions import (
    VoltagePointError,
)
from ...tools.qua_tools import (
    is_qua_type,
    validate_duration,
    VoltageLevelType,
    DurationType,
)

__all__ = [
    "VoltageTuningPoint",
    "VoltageSequence",
]

# --- Constants ---
MIN_PULSE_DURATION_NS = 16
CLOCK_CYCLE_NS = 4
INTEGRATED_VOLTAGE_SCALING_FACTOR = 1024
COMPENSATION_SCALING_FACTOR = 1.0 / INTEGRATED_VOLTAGE_SCALING_FACTOR
MIN_COMPENSATION_DURATION_NS = 16
DEFAULT_QUA_COMPENSATION_DURATION_NS = 48
DEFAULT_PULSE_NAME = "half_max_square"
# QUA_COMPENSATION_GAP_NS = 96 # Not used if Channel methods handle timing
RAMP_QUA_DELAY_CYCLES = 9  # Approx delay for QUA ramp calculations


class VoltageSequence:
    """
    Manages the generation of a QUA sequence for setting and adjusting DC voltages
    on a set of gate channels defined within a GateSet.

    The user is responsible for ensuring that each QUAM Channel object in the
    GateSet has an operation defined in the QUA configuration named DEFAULT_PULSE_NAME,
    which is '250mV_square' by default. This operation should correspond to a pulse
    of MIN_PULSE_DURATION_NS (16ns) with a waveform whose constant sample value is
    DEFAULT_BASE_WF_SAMPLE (0.25V).
    This class does not modify the QUA configuration.

    Important behavior:
    - Unspecified channels are treated as 0 V on every call. Each
      operation (step/ramp/point) receives a fresh set of target voltages and
      any channel not included is driven to 0 V for that operation.
    - When used with a VirtualGateSet, the same rule applies to virtual gates:
      any virtual gate not explicitly provided in a call is assumed to be 0 V
      for that operation. This effectively removes prior contributions of those
      virtual gates from the resulting physical voltages. To preserve a prior
      virtual configuration, include all relevant virtual gates (and their
      values) in each call, or operate directly on physical gates.
    """

    def __init__(self, gate_set: GateSet, track_integrated_voltage: bool = True):
        """
        Initializes the VoltageSequence.

        Args:
            gate_set: The GateSet instance this sequence will operate on.
        """
        self.gate_set: GateSet = gate_set
        self.state_trackers: Dict[str, SequenceStateTracker] = {
            ch_name: SequenceStateTracker(ch_name)
            for ch_name in self.gate_set.channels.keys()
        }
        self._temp_qua_vars: Dict[str, QuaVariable] = {}  # For ramp_rate etc.
        self._track_integrated_voltage: bool = track_integrated_voltage
        warnings.warn(
            "When using this class outside the scope of qua-dashboards video_mode, please contact your Customer Success Physicist at Quantum Machines. "
            "Complete validation of this framework is currently in progress, and it will be fully available soon."
        )

    def _get_temp_qua_var(self, name_suffix: str, var_type=fixed) -> QuaVariable:
        """Gets or declares a temporary QUA variable for internal calculations."""
        # Use a prefix related to the VoltageSequence instance if multiple exist
        # For now, simple suffix based on usage.
        internal_name = f"_vseq_tmp_{name_suffix}"
        if internal_name not in self._temp_qua_vars:
            self._temp_qua_vars[internal_name] = declare(var_type)
        return self._temp_qua_vars[internal_name]

    def _play_step_on_channel(
        self,
        channel: SingleChannel,
        delta_v: VoltageLevelType,
        duration: DurationType,
    ):
        """Plays a scaled step on a single channel."""
        DEFAULT_WF_AMPLITUDE = channel.operations[DEFAULT_PULSE_NAME].amplitude
        DEFAULT_AMPLITUDE_BITSHIFT = int(np.log2(1 / DEFAULT_WF_AMPLITUDE))
        MIN_PULSE_DURATION_NS = channel.operations[DEFAULT_PULSE_NAME].length
        py_duration = 0
        if not is_qua_type(duration):
            py_duration = int(float(str(duration)))

        if py_duration == 0 and not is_qua_type(duration):
            return

        if is_qua_type(delta_v):
            scaled_amp = delta_v << DEFAULT_AMPLITUDE_BITSHIFT
        else:
            scaled_amp = np.round(delta_v * (1.0 / DEFAULT_WF_AMPLITUDE), 10)
        duration_cycles = duration >> 2  # Convert ns to clock cycles

        if is_qua_type(duration):
            # If duration is QUA, it must be in clock cycles for play override
            # Assuming QUA duration is already in ns, convert to cycles
            channel.play(
                DEFAULT_PULSE_NAME,
                amplitude_scale=scaled_amp,
                duration=duration_cycles,
                validate=False,  # Do not validate as pulse may not exist yet
            )
        else:  # Fixed Python duration
            if py_duration == MIN_PULSE_DURATION_NS:
                channel.play(
                    DEFAULT_PULSE_NAME,
                    amplitude_scale=scaled_amp,
                    duration=duration_cycles,
                    validate=False,  # Do not validate as pulse may not exist yet
                )
            elif py_duration > 0:
                channel.play(
                    DEFAULT_PULSE_NAME,
                    amplitude_scale=scaled_amp,
                    duration=py_duration >> 2,
                    validate=False,  # Do not validate as pulse may not exist yet
                )

    def _play_ramp_on_channel(
        self,
        channel: SingleChannel,
        delta_v: VoltageLevelType,
        ramp_duration: DurationType,
        hold_duration: DurationType,
    ):
        """Plays a ramp then holds on a single channel."""
        py_ramp_duration = 0
        if not is_qua_type(ramp_duration):
            py_ramp_duration = int(float(str(ramp_duration)))

        ramp_duration_cycles = (
            ramp_duration >> 2 if is_qua_type(ramp_duration) else py_ramp_duration >> 2
        )

        if is_qua_type(delta_v) or is_qua_type(ramp_duration):
            ramp_rate = self._get_temp_qua_var(f"{channel.name}_ramp_rate")
            assign(ramp_rate, delta_v * Math.div(1.0, ramp_duration))
            channel.play(
                ramp(ramp_rate),
                duration=ramp_duration_cycles,
                validate=False,
            )
        else:
            py_delta_v = float(str(delta_v))
            if py_ramp_duration > 0:
                ramp_rate_val = py_delta_v / py_ramp_duration
                channel.play(
                    ramp(ramp_rate_val),
                    duration=ramp_duration_cycles,
                    validate=False,
                )

        py_hold_duration = 0
        if not is_qua_type(hold_duration):
            py_hold_duration = int(float(str(hold_duration)))

        if is_qua_type(hold_duration):
            wait_cycles = hold_duration >> 2
            if is_qua_type(ramp_duration):  # Adjust for QUA ramp calculation time
                wait_cycles -= RAMP_QUA_DELAY_CYCLES
            with if_(wait_cycles > 0):
                channel.wait(wait_cycles)
        else:
            if py_hold_duration > 0:
                channel.wait(py_hold_duration >> 2)

    def _common_voltages_change(
        self,
        target_voltages_dict: Dict[str, VoltageLevelType],
        duration: DurationType,
        ramp_duration: Optional[DurationType] = None,
    ):
        """Common logic for step_to_voltages and ramp_to_voltages."""
        validate_duration(duration, "duration")
        if ramp_duration is not None:
            validate_duration(ramp_duration, "ramp_duration")
            if is_qua_type(ramp_duration):
                print(  # Changed from warn to print as warn is not imported
                    "Guidance: Using QUA variable for `ramp_duration`. "
                    "Ensure hold `duration` is sufficient."
                )

        full_target_voltages_dict = self.gate_set.resolve_voltages(target_voltages_dict)

        for ch_name, target_voltage in full_target_voltages_dict.items():
            if ch_name not in self.gate_set.channels:
                print(f"Warning: Channel '{ch_name}' not in GateSet. Skipping.")
                continue

            tracker = self.state_trackers[ch_name]
            channel_obj = self.gate_set.channels[ch_name]
            current_v = tracker.current_level

            delta_v: VoltageLevelType
            if is_qua_type(target_voltage) or is_qua_type(current_v):
                delta_v = target_voltage - current_v
            else:
                delta_v = float(str(target_voltage)) - float(str(current_v))

            if self._track_integrated_voltage:
                tracker.update_integrated_voltage(
                    target_voltage,
                    duration,
                    ramp_duration,
                )

            if ramp_duration is None or (
                not is_qua_type(ramp_duration) and int(float(str(ramp_duration))) == 0
            ):
                self._play_step_on_channel(channel_obj, delta_v, duration)
            else:
                self._play_ramp_on_channel(
                    channel_obj,
                    delta_v,
                    ramp_duration,
                    duration,
                )
            tracker.current_level = target_voltage

    def step_to_voltages(
        self, voltages: Dict[str, VoltageLevelType], duration: DurationType
    ):
        """
        Steps all specified channels directly to the given voltage levels.

        Creates immediate voltage changes without ramping. Any channel not specified in
        `voltages` will be set to zero volts for the duration. This method is useful
        when you need precise, instantaneous voltage transitions for operations
        like loading or measuring quantum dots.

        Note on virtual gates:
            When this sequence is created from a VirtualGateSet, any virtual gate
            not included in `voltages` is assumed to be 0 V for this call. As a
            result, previous contributions from such virtual gates are cleared in
            the resolved physical voltages. Include all relevant virtual gates in
            each call if you want to maintain their contributions.

        Args:
            voltages: A dictionary mapping channel names to their target
                voltages (in volts). Channels not included will be set to 0.0V.
                Each voltage level can be a fixed value or a QUA variable.
            duration: The duration (ns) to hold the voltages, must be >16ns and
                a multiple of 4ns. Can be a fixed value or a QUA variable.

        Example:
            >>> with qua.program() as prog:
            ...     voltage_seq = gate_set.new_sequence()
            ...     # Step plunger gates to loading voltages instantly
            ...     voltage_seq.step_to_voltages({"P1": 0.3, "P2": 0.1}, duration=1000)
            ...     # Any channel not specified (e.g., "B1") will be set to 0.0V
            ...     voltage_seq.step_to_voltages({"P1": 0.5}, duration=500)
        """
        self._common_voltages_change(voltages, duration, ramp_duration=None)

    def ramp_to_voltages(
        self,
        voltages: Dict[str, VoltageLevelType],
        duration: DurationType,
        ramp_duration: DurationType,
    ):
        """
        Ramps all specified channels to the given voltage levels, then holds.

        Provides smooth voltage transitions useful for avoiding voltage spikes
        that could affect sensitive quantum systems. The ramp creates a linear
        transition from the current voltage to the target voltage over the
        specified ramp duration.

        Note on virtual gates:
            When this sequence is created from a VirtualGateSet, any virtual gate
            not included in `voltages` is assumed to be 0 V for this call. As a
            result, previous contributions from such virtual gates are cleared in
            the resolved physical voltages. Include all relevant virtual gates in
            each call if you want to maintain their contributions.

        Args:
            voltages: A dictionary mapping channel names to their target
                voltage levels (in volts). Channels not included will be set to 0.0V.
                Each voltage level can be a fixed value or a QUA variable.
            duration: The duration (ns) to hold the voltages after the ramp. Must be
                >16ns and a multiple of 4ns. Can be a fixed value or a QUA variable.
            ramp_duration: The duration (ns) of the ramp. Can be a fixed value or a QUA
                variable.

        Example:
            >>> with qua.program() as prog:
            ...     voltage_seq = gate_set.new_sequence()
            ...     # Smooth ramp to avoid voltage spikes on sensitive gates
            ...     voltage_seq.ramp_to_voltages(
            ...         voltages={"P1": 0.0, "B1": -0.1},
            ...         duration=500,
            ...         ramp_duration=40
            ...     )
            ...     # Can use QUA variables for dynamic control
            ...     ramp_time = declare(int)
            ...     assign(ramp_time, 80)
            ...     voltage_seq.ramp_to_voltages(
            ...         voltages={"P2": 0.2}, duration=1000, ramp_duration=ramp_time
            ...     )
        """
        self._common_voltages_change(voltages, duration, ramp_duration=ramp_duration)

    def step_to_point(self, name: str, duration: Optional[DurationType] = None):
        """
        Steps all channels to the voltages defined in a predefined tuning point.

        This method enables quick transitions to well-defined system states that
        were configured using GateSet.add_point(). It automatically applies
        voltages to all channels defined in the tuning point.

        Args:
            name: The name of the predefined VoltageTuningPoint.
            duration: Optional. The duration (ns) to hold the voltages.
                If None, the default duration from the VoltageTuningPoint is used.
                Must be >16ns and a multiple of 4ns. Can be a fixed value or a QUA
                variable.

        Example:
            >>> # First, define tuning points on the GateSet
            >>> gate_set.add_point("load", {"P1": 0.5, "P2": -0.2}, duration=1000)
            >>> gate_set.add_point("measure", {"P1": 0.3, "P2": 0.1}, duration=500)
            >>>
            >>> with qua.program() as prog:
            ...     voltage_seq = gate_set.new_sequence()
            ...     # Use predefined voltage configurations
            ...     voltage_seq.step_to_point("load")  # Uses default 1000ns duration
            ...     voltage_seq.step_to_point("measure", duration=2000)  # Override duration
        """
        tuning_point_macro = self.gate_set.macros.get(name)
        if not isinstance(tuning_point_macro, VoltageTuningPoint):
            raise VoltagePointError(
                f"Macro '{name}' is not a valid VoltageTuningPoint or not found."
            )
        tuning_point: VoltageTuningPoint = tuning_point_macro
        effective_duration = duration if duration is not None else tuning_point.duration
        self._common_voltages_change(
            tuning_point.voltages, effective_duration, ramp_duration=None
        )

    def ramp_to_point(
        self,
        name: str,
        ramp_duration: DurationType,
        duration: Optional[DurationType] = None,
    ):
        """
        Ramps all channels to the voltages defined in a predefined tuning point.

        Combines the smooth transitions of ramping with the convenience of predefined
        voltage states. This is particularly useful for sensitive transitions to
        well-characterized system configurations.

        Args:
            name: The name of the predefined VoltageTuningPoint.
            ramp_duration: The duration (ns) of the ramp. Must be >16ns and a multiple
                of 4ns. Can be a fixed value or a QUA variable.
            duration: Optional. The duration (ns) to hold the voltages after ramp.
                If None, the default duration from the VoltageTuningPoint is used.
                Must be >16ns and a multiple of 4ns. Can be a fixed value or a QUA
                variable.

        Example:
            >>> # First, define tuning points on the GateSet
            >>> gate_set.add_point("idle", {"P1": 0.1, "P2": -0.05}, duration=1000)
            >>> gate_set.add_point("readout", {"P1": 0.3, "P2": 0.1}, duration=2000)
            >>>
            >>> with qua.program() as prog:
            ...     voltage_seq = gate_set.new_sequence()
            ...     # Smooth ramp to predefined configurations
            ...     voltage_seq.ramp_to_point("idle", ramp_duration=50, duration=1000)
            ...     # Uses default duration of 2000ns:
            ...     voltage_seq.ramp_to_point("readout", ramp_duration=100)
        """
        tuning_point_macro = self.gate_set.macros.get(name)
        if not isinstance(tuning_point_macro, VoltageTuningPoint):
            raise VoltagePointError(
                f"Macro '{name}' is not a valid VoltageTuningPoint or not found."
            )
        tuning_point: VoltageTuningPoint = tuning_point_macro
        effective_duration = duration if duration is not None else tuning_point.duration
        self._common_voltages_change(
            tuning_point.voltages,
            effective_duration,
            ramp_duration=ramp_duration,
        )

    def _calculate_python_compensation_params(
        self,
        tracker: SequenceStateTracker,
        max_voltage: float,
    ) -> Tuple[float, int]:
        """
        Calculates compensation pulse amplitude and duration for Python-only values.
        Returns (amplitude, duration).
        """
        py_int_v = int(float(str(tracker.integrated_voltage)))
        if py_int_v == 0:
            return 0.0, 0

        ideal_dur = abs(py_int_v * COMPENSATION_SCALING_FACTOR / max_voltage)
        py_comp_dur = max(ideal_dur, MIN_COMPENSATION_DURATION_NS)
        py_comp_dur = (
            (int(np.ceil(py_comp_dur)) + CLOCK_CYCLE_NS - 1)
            // CLOCK_CYCLE_NS
            * CLOCK_CYCLE_NS
        )
        py_comp_dur = max(py_comp_dur, DEFAULT_QUA_COMPENSATION_DURATION_NS)

        py_comp_amp = 0.0
        if py_comp_dur > 0:
            py_comp_amp = -(py_int_v * COMPENSATION_SCALING_FACTOR) / py_comp_dur
            py_comp_amp = np.clip(py_comp_amp, -max_voltage, max_voltage)
        return py_comp_amp, py_comp_dur

    def _calculate_qua_compensation_params(
        self,
        tracker: SequenceStateTracker,
        max_voltage: float,
        channel_id_str: str,
    ) -> Tuple[QuaScalarExpression, QuaScalarExpression]:
        """
        Generates QUA code to calculate compensation pulse amplitude and duration.
        Returns (qua_amplitude_expression, qua_duration_expression).
        """
        integrated_v = tracker.integrated_voltage
        # current_v = tracker.current_level # Not directly needed for amp/dur calc here

        eval_int_v = self._get_temp_qua_var(f"{channel_id_str}_eval_int_v", int)
        q_comp_dur_i = self._get_temp_qua_var(f"{channel_id_str}_comp_dur_i", int)
        q_comp_dur_4ns = self._get_temp_qua_var(f"{channel_id_str}_comp_dur_4", int)
        q_comp_amp = self._get_temp_qua_var(f"{channel_id_str}_comp_amp", fixed)

        assign(eval_int_v, integrated_v)

        assign(
            q_comp_dur_i,
            Cast.mul_int_by_fixed(
                Math.abs(eval_int_v),
                COMPENSATION_SCALING_FACTOR / max_voltage,
            ),
        )
        with if_(q_comp_dur_i < MIN_COMPENSATION_DURATION_NS):
            assign(q_comp_dur_i, MIN_COMPENSATION_DURATION_NS)
        assign(q_comp_dur_4ns, (q_comp_dur_i + 3) >> 2 << 2)
        with if_(q_comp_dur_4ns < DEFAULT_QUA_COMPENSATION_DURATION_NS):
            assign(q_comp_dur_4ns, DEFAULT_QUA_COMPENSATION_DURATION_NS)

        with if_(eval_int_v == 0):
            assign(q_comp_amp, 0.0)
        with else_():
            with if_(q_comp_dur_4ns > 0):
                inv_dur = Math.div(1.0, q_comp_dur_4ns)
                assign(
                    q_comp_amp,
                    -Cast.mul_int_by_fixed(eval_int_v, COMPENSATION_SCALING_FACTOR)
                    * inv_dur,
                )
            with else_():
                assign(q_comp_amp, 0.0)
        return q_comp_amp, q_comp_dur_4ns

    def apply_compensation_pulse(self, max_voltage: float = 0.49):
        """
        To be included in future release: Use with caution

        Apply compensation pulse to each channel to counteract integrated voltage drift.

        When integrated voltage tracking is enabled, this method calculates and applies
        pulses to neutralize accumulated voltage drift on AC-coupled lines. The
        compensation amplitude and duration are optimized to stay within voltage limits.

        Args:
            max_voltage: The maximum absolute amplitude for the compensation pulse.

        Example:
            >>> with qua.program() as prog:
            ...     # Enable integrated voltage tracking
            ...     voltage_seq = gate_set.new_sequence(track_integrated_voltage=True)
            ...
            ...     # Perform voltage operations that accumulate drift
            ...     voltage_seq.step_to_voltages({"P1": 0.3}, duration=5000)
            ...     voltage_seq.ramp_to_voltages({"P1": 0.0}, duration=1000, ramp_duration=100)
            ...
            ...     # Apply compensation to counteract accumulated drift
            ...     voltage_seq.apply_compensation_pulse()  # Use default 0.49V limit
            ...     voltage_seq.apply_compensation_pulse(max_voltage=0.3)  # Custom limit

        Note:
            Only available when track_integrated_voltage=True is set in new_sequence().
        """
        ### To be implemented in future release. Use with caution!

        # if not self._track_integrated_voltage:
        #     raise ValueError(
        #         "apply_compensation_pulse is not supported when integrated voltage is not tracked."
        #     )
        # if max_voltage <= 0:
        #     raise ValueError("max_voltage must be positive.")

        # for ch_name, channel_obj in self.gate_set.channels.items():
        #     DEFAULT_WF_AMPLITUDE = channel_obj.operations[DEFAULT_PULSE_NAME].amplitude
        #     DEFAULT_AMPLITUDE_BITSHIFT = int(np.log2(1 / DEFAULT_WF_AMPLITUDE))

        #     tracker = self.state_trackers[ch_name]
        #     current_v = tracker.current_level

        #     comp_amp_val: VoltageLevelType
        #     comp_dur_val: DurationType  # ns

        #     if not is_qua_type(tracker.integrated_voltage) and not is_qua_type(
        #         current_v
        #     ):
        #         py_comp_amp, py_comp_dur = self._calculate_python_compensation_params(
        #             tracker, max_voltage
        #         )
        #         if py_comp_dur == 0:  # No pulse needed
        #             tracker.current_level = py_comp_amp  # Should be 0.0
        #             continue

        #         delta_v = py_comp_amp - float(str(current_v))
        #         if is_qua_type(delta_v):
        #             scaled_amp = delta_v << DEFAULT_AMPLITUDE_BITSHIFT
        #         else:
        #             scaled_amp = np.round(delta_v * (1.0 / DEFAULT_WF_AMPLITUDE), 10)
        #         channel_obj.play(
        #             DEFAULT_PULSE_NAME,
        #             amplitude_scale=scaled_amp,
        #             duration=py_comp_dur >> 2,
        #             validate=False,  # Do not validate as pulse may not exist yet
        #         )
        #         comp_amp_val, comp_dur_val = py_comp_amp, py_comp_dur
        #     else:
        #         q_comp_amp, q_comp_dur_4ns = self._calculate_qua_compensation_params(
        #             tracker, max_voltage, channel_obj.name
        #         )
        #         delta_v_q = q_comp_amp - current_v
        #         scaled_amp_q = delta_v_q << DEFAULT_AMPLITUDE_BITSHIFT
        #         with if_(q_comp_dur_4ns > 0):
        #             channel_obj.play(
        #                 DEFAULT_PULSE_NAME,
        #                 amplitude_scale=scaled_amp_q,
        #                 duration=q_comp_dur_4ns >> 2,
        #                 validate=False,  # Do not validate as pulse may not exist yet
        #             )
        #         comp_amp_val, comp_dur_val = q_comp_amp, q_comp_dur_4ns

        #     tracker.current_level = comp_amp_val

        raise NotImplementedError(
            "Compensation pulses not yet implemented, to be included in future release. Use with caution"
        )

    def _perform_ramp_to_zero_with_duration(
        self,
        channel_obj: SingleChannel,
        tracker: SequenceStateTracker,
        ramp_duration: int,
    ):
        """Helper for ramp_to_zero when a specific duration is provided."""
        DEFAULT_WF_AMPLITUDE = channel_obj.operations[DEFAULT_PULSE_NAME].amplitude
        current_v = tracker.current_level
        validate_duration(ramp_duration, "ramp_duration")

        if is_qua_type(current_v):
            ramp_rate = self._get_temp_qua_var(f"{channel_obj.name}_r2z_rate")
            with if_(ramp_duration > 0):
                assign(ramp_rate, -current_v * Math.div(1.0, ramp_duration))
                channel_obj.play(
                    ramp(ramp_rate),
                    duration=ramp_duration >> 2,
                )
            with else_():  # Duration is 0, effectively a step
                channel_obj.play(
                    DEFAULT_PULSE_NAME,
                    amplitude_scale=-current_v
                    * np.round(1.0 / DEFAULT_WF_AMPLITUDE, 10),
                    duration=ramp_duration >> 2,
                    validate=False,  # Do not validate as pulse may not exist yet
                )
        else:
            py_curr_v = float(str(current_v))
            if ramp_duration > 0 and py_curr_v != 0.0:
                rate_val = -py_curr_v / ramp_duration
                channel_obj.play(
                    ramp(rate_val),
                    duration=ramp_duration >> 2,
                    validate=False,
                )
            elif py_curr_v != 0.0:  # Duration is 0, step
                delta_v_to_zero = -py_curr_v
                if is_qua_type(delta_v_to_zero):
                    scaled_amp_to_zero = delta_v_to_zero * (1.0 / DEFAULT_WF_AMPLITUDE)
                else:
                    scaled_amp_to_zero = np.round(
                        delta_v_to_zero * (1.0 / DEFAULT_WF_AMPLITUDE), 10
                    )
                channel_obj.play(
                    DEFAULT_PULSE_NAME,
                    amplitude_scale=scaled_amp_to_zero,
                    duration=ramp_duration >> 2,
                    validate=False,  # Do not validate as pulse may not exist yet
                )

    def ramp_to_zero(self, ramp_duration: Optional[int] = None):
        """
        Ramps the voltage on all channels in the GateSet to zero

        Also resets integrated voltage tracking.

        Args:
            ramp_duration: Optional. The duration (ns) of the ramp to zero.
                If None, QUA's `ramp_to_zero` command is used for an immediate ramp.
                Must be >16ns and a multiple of 4ns. Can be a fixed value or a QUA
                variable.

        Example:
            >>> with qua.program() as prog:
            ...     voltage_seq = gate_set.new_sequence()
            ...
            ...     # Set various voltages
            ...     voltage_seq.step_to_voltages({"P1": 0.3, "P2": 0.1}, duration=1000)
            ...
            ...     # Different ways to return to zero
            ...     voltage_seq.ramp_to_zero()  # Immediate ramp using QUA built-in
            ...     voltage_seq.ramp_to_zero(ramp_duration=100)  # Controlled ramp over 100ns
            ...
            ...     # All channels now at 0V, integrated voltage tracking reset
        """
        for ch_name, channel_obj in self.gate_set.channels.items():
            tracker = self.state_trackers[ch_name]

            if ramp_duration is None:
                ramp_to_zero(channel_obj.name)
            else:
                self._perform_ramp_to_zero_with_duration(
                    channel_obj, tracker, ramp_duration
                )

            tracker.current_level = 0.0

            if self._track_integrated_voltage:
                tracker.reset_integrated_voltage()

    def apply_to_config(self, config: dict):
        """
        Placeholder for ensuring QUA config has necessary definitions.

        In this model, this class does not directly modify the config.
        This method could be used for validation or to provide guidance.

        Args:
            config: The QUA configuration dictionary (for inspection).
        """
        # TODO Add 250mV pulses to config
        # for channel in self.gate_set.channels.values():
        #     pulse_name = channel.name + PULSE_SUFFIX
