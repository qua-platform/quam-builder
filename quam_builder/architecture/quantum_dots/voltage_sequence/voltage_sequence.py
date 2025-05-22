from typing import Dict, Optional, Any, Union, List, Tuple

import numpy as np
from qm.qua import (
    declare,
    assign,
    play,
    fixed,
    Cast,
    amp,
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

from quam_builder.architecture.quantum_dots.voltage_sequence.gate_set import (
    GateSet,
    VoltageTuningPoint,
)

from .sequence_state_tracker import SequenceStateTracker
from ..exceptions import (
    VoltagePointError,
)
from ..utils import is_qua_type, validate_duration, VoltageLevelType, DurationType

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
# QUA_COMPENSATION_GAP_NS = 96 # Not used if Channel methods handle timing
RAMP_QUA_DELAY_CYCLES = 9  # Approx delay for QUA ramp calculations

DEFAULT_PULSE_NAME = "250mV_square"
DEFAULT_WF_AMPLITUDE = 0.25


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

    def _get_temp_qua_var(self, name_suffix: str, var_type=fixed) -> QuaVariable:
        """Gets or declares a temporary QUA variable for internal calculations."""
        # Use a prefix related to the VoltageSequence instance if multiple exist
        # For now, simple suffix based on usage.
        internal_name = f"_vseq_tmp_{name_suffix}"
        if internal_name not in self._temp_qua_vars:
            self._temp_qua_vars[internal_name] = declare(var_type, name=internal_name)
        return self._temp_qua_vars[internal_name]

    def _play_step_on_channel(
        self,
        channel: SingleChannel,
        delta_v: VoltageLevelType,
        duration_ns: DurationType,
    ):
        """Plays a scaled step on a single channel."""
        py_duration_ns = 0
        if not is_qua_type(duration_ns):
            py_duration_ns = int(float(str(duration_ns)))

        if py_duration_ns == 0 and not is_qua_type(duration_ns):
            return

        if is_qua_type(delta_v):
            scaled_amp = delta_v * (1.0 / DEFAULT_WF_AMPLITUDE)
        else:
            scaled_amp = np.round(delta_v * (1.0 / DEFAULT_WF_AMPLITUDE), 10)
        duration_cycles = duration_ns >> 2  # Convert ns to clock cycles

        if is_qua_type(duration_ns):
            # If duration is QUA, it must be in clock cycles for play override
            # Assuming QUA duration_ns is already in ns, convert to cycles
            channel.play(
                DEFAULT_PULSE_NAME,
                amplitude_scale=scaled_amp,
                duration=duration_cycles,
                validate=False,  # Do not validate as pulse may not exist yet
            )
        else:  # Fixed Python duration
            if py_duration_ns == MIN_PULSE_DURATION_NS:
                channel.play(
                    DEFAULT_PULSE_NAME,
                    amplitude_scale=scaled_amp,
                    duration=duration_cycles,
                    validate=False,  # Do not validate as pulse may not exist yet
                )
            elif py_duration_ns > 0:
                channel.play(
                    DEFAULT_PULSE_NAME,
                    amplitude_scale=scaled_amp,
                    duration=py_duration_ns >> 2,
                    validate=False,  # Do not validate as pulse may not exist yet
                )

    def _play_ramp_on_channel(
        self,
        channel: SingleChannel,
        delta_v: VoltageLevelType,
        ramp_duration_ns: DurationType,
        hold_duration_ns: DurationType,
    ):
        """Plays a ramp then holds on a single channel."""
        py_ramp_duration_ns = 0
        if not is_qua_type(ramp_duration_ns):
            py_ramp_duration_ns = int(float(str(ramp_duration_ns)))

        ramp_duration_cycles = (
            ramp_duration_ns >> 2
            if is_qua_type(ramp_duration_ns)
            else py_ramp_duration_ns >> 2
        )

        if ramp_duration_cycles > 0:
            if is_qua_type(delta_v) or is_qua_type(ramp_duration_ns):
                ramp_rate = self._get_temp_qua_var(f"{channel.name}_ramp_rate")
                assign(ramp_rate, delta_v * Math.div(1.0, ramp_duration_ns))
                channel.play(
                    ramp(ramp_rate),
                    duration=ramp_duration_cycles,
                )
            else:
                py_delta_v = float(str(delta_v))
                if py_ramp_duration_ns > 0:
                    ramp_rate_val = py_delta_v / py_ramp_duration_ns
                    channel.play(
                        ramp(ramp_rate_val),
                        duration=ramp_duration_cycles,
                    )

        py_hold_duration_ns = 0
        if not is_qua_type(hold_duration_ns):
            py_hold_duration_ns = int(float(str(hold_duration_ns)))

        if is_qua_type(hold_duration_ns):
            wait_cycles = hold_duration_ns >> 2
            if is_qua_type(ramp_duration_ns):  # Adjust for QUA ramp calculation time
                wait_cycles -= RAMP_QUA_DELAY_CYCLES
            with if_(wait_cycles > 0):
                channel.wait(wait_cycles)
        else:
            if py_hold_duration_ns > 0:
                channel.wait(py_hold_duration_ns >> 2)

    def _common_level_change(
        self,
        target_levels_dict: Dict[str, VoltageLevelType],
        duration_ns: DurationType,
        ramp_duration_ns: Optional[DurationType] = None,
    ):
        """Common logic for step_to_level and ramp_to_level."""
        validate_duration(duration_ns, "duration_ns")
        if ramp_duration_ns is not None:
            validate_duration(ramp_duration_ns, "ramp_duration_ns")
            if is_qua_type(ramp_duration_ns):
                print(  # Changed from warn to print as warn is not imported
                    "Guidance: Using QUA variable for `ramp_duration_ns`. "
                    "Ensure hold `duration_ns` is sufficient."
                )

        full_target_levels_dict = self.gate_set.resolve_voltages(target_levels_dict)

        for ch_name, target_voltage in full_target_levels_dict.items():
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
                    duration_ns,
                    ramp_duration_ns,
                )

            if ramp_duration_ns is None or (
                not is_qua_type(ramp_duration_ns)
                and int(float(str(ramp_duration_ns))) == 0
            ):
                self._play_step_on_channel(channel_obj, delta_v, duration_ns)
            else:
                self._play_ramp_on_channel(
                    channel_obj,
                    delta_v,
                    ramp_duration_ns,
                    duration_ns,
                )
            tracker.current_level = target_voltage

    def step_to_level(
        self, levels: Dict[str, VoltageLevelType], duration: DurationType
    ):
        """
        Steps all specified channels directly to the given voltage levels.

        Args:
            levels: A dictionary mapping channel names to their target
                voltage levels.
            duration: The duration (ns) to hold the voltages.
        """
        self._common_level_change(levels, duration, ramp_duration_ns=None)

    def ramp_to_level(
        self,
        levels: Dict[str, VoltageLevelType],
        duration: DurationType,
        ramp_duration: DurationType,
    ):
        """
        Ramps all specified channels to the given voltage levels, then holds.

        Args:
            levels: A dictionary mapping channel names to their target
                voltage levels.
            duration: The duration (ns) to hold the voltages after the ramp.
            ramp_duration: The duration (ns) of the ramp.
        """
        self._common_level_change(levels, duration, ramp_duration_ns=ramp_duration)

    def go_to_point(self, name: str, duration: Optional[int] = None):
        """
        Steps all channels to the voltages defined in a predefined tuning point.

        Args:
            name: The name of the predefined VoltageTuningPoint.
            duration: Optional. The duration (ns) to hold the voltages.
                If None, the default duration from the VoltageTuningPoint is used.
        """
        tuning_point_macro = self.gate_set.macros.get(name)
        if not isinstance(tuning_point_macro, VoltageTuningPoint):
            raise VoltagePointError(
                f"Macro '{name}' is not a valid VoltageTuningPoint or not found."
            )
        tuning_point: VoltageTuningPoint = tuning_point_macro
        effective_duration = duration if duration is not None else tuning_point.duration
        self._common_level_change(
            tuning_point.voltages, effective_duration, ramp_duration_ns=None
        )

    def ramp_to_point(
        self,
        name: str,
        ramp_duration: DurationType,
        duration: Optional[DurationType] = None,
    ):
        """
        Ramps all channels to the voltages defined in a predefined tuning point.

        Args:
            name: The name of the predefined VoltageTuningPoint.
            ramp_duration: The duration (ns) of the ramp.
            duration: Optional. The duration (ns) to hold the voltages after ramp.
                If None, the default duration from the VoltageTuningPoint is used.
        """
        tuning_point_macro = self.gate_set.macros.get(name)
        if not isinstance(tuning_point_macro, VoltageTuningPoint):
            raise VoltagePointError(
                f"Macro '{name}' is not a valid VoltageTuningPoint or not found."
            )
        tuning_point: VoltageTuningPoint = tuning_point_macro
        effective_duration = duration if duration is not None else tuning_point.duration
        self._common_level_change(
            tuning_point.voltages,
            effective_duration,
            ramp_duration_ns=ramp_duration,
        )

    def _calculate_python_compensation_params(
        self,
        tracker: SequenceStateTracker,
        max_voltage: float,
    ) -> Tuple[float, int]:
        """
        Calculates compensation pulse amplitude and duration for Python-only values.
        Returns (amplitude, duration_ns).
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
        Returns (qua_amplitude_expression, qua_duration_ns_expression).
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
        Applies a compensation pulse to each channel.

        Args:
            max_voltage: The maximum absolute amplitude for the compensation pulse.
        """
        if not self._track_integrated_voltage:
            raise ValueError(
                "apply_compensation_pulse is not supported when integrated voltage is not tracked."
            )
        if max_voltage <= 0:
            raise ValueError("max_voltage must be positive.")

        for ch_name, channel_obj in self.gate_set.channels.items():
            tracker = self.state_trackers[ch_name]
            current_v = tracker.current_level

            comp_amp_val: VoltageLevelType
            comp_dur_val: DurationType  # ns

            if not is_qua_type(tracker.integrated_voltage) and not is_qua_type(
                current_v
            ):
                py_comp_amp, py_comp_dur = self._calculate_python_compensation_params(
                    tracker, max_voltage
                )
                if py_comp_dur == 0:  # No pulse needed
                    tracker.current_level = py_comp_amp  # Should be 0.0
                    continue

                delta_v = py_comp_amp - float(str(current_v))
                if is_qua_type(delta_v):
                    scaled_amp = delta_v * np.round(1.0 / DEFAULT_WF_AMPLITUDE, 10)
                else:
                    scaled_amp = np.round(delta_v * (1.0 / DEFAULT_WF_AMPLITUDE), 10)
                channel_obj.play(
                    DEFAULT_PULSE_NAME,
                    amplitude_scale=scaled_amp,
                    duration=py_comp_dur >> 2,
                    validate=False,  # Do not validate as pulse may not exist yet
                )
                comp_amp_val, comp_dur_val = py_comp_amp, py_comp_dur
            else:
                q_comp_amp, q_comp_dur_4ns = self._calculate_qua_compensation_params(
                    tracker, max_voltage, channel_obj.name
                )
                delta_v_q = q_comp_amp - current_v
                scaled_amp_q = delta_v_q * (1.0 / DEFAULT_WF_AMPLITUDE)
                with if_(q_comp_dur_4ns > 0):
                    channel_obj.play(
                        DEFAULT_PULSE_NAME,
                        amplitude_scale=scaled_amp_q,
                        duration=q_comp_dur_4ns >> 2,
                        validate=False,  # Do not validate as pulse may not exist yet
                    )
                comp_amp_val, comp_dur_val = q_comp_amp, q_comp_dur_4ns

            tracker.current_level = comp_amp_val

    def _perform_ramp_to_zero_with_duration(
        self,
        channel_obj: SingleChannel,
        tracker: SequenceStateTracker,
        ramp_duration_ns: int,
    ):
        """Helper for ramp_to_zero when a specific duration is provided."""
        current_v = tracker.current_level
        validate_duration(ramp_duration_ns, "ramp_duration_ns")

        if is_qua_type(current_v):
            ramp_rate = self._get_temp_qua_var(f"{channel_obj.name}_r2z_rate")
            with if_(ramp_duration_ns > 0):
                assign(ramp_rate, -current_v * Math.div(1.0, ramp_duration_ns))
                channel_obj.play(
                    ramp(ramp_rate),
                    duration=ramp_duration_ns >> 2,
                )
            with else_():  # Duration is 0, effectively a step
                channel_obj.play(
                    DEFAULT_PULSE_NAME,
                    amplitude_scale=-current_v
                    * np.round(1.0 / DEFAULT_WF_AMPLITUDE, 10),
                    duration=ramp_duration_ns >> 2,
                    validate=False,  # Do not validate as pulse may not exist yet
                )
        else:
            py_curr_v = float(str(current_v))
            if ramp_duration_ns > 0 and py_curr_v != 0.0:
                rate_val = -py_curr_v / ramp_duration_ns
                channel_obj.play(
                    ramp(rate_val),
                    duration=ramp_duration_ns >> 2,
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
                    duration=ramp_duration_ns >> 2,
                    validate=False,  # Do not validate as pulse may not exist yet
                )

    def ramp_to_zero(self, ramp_duration_ns: Optional[int] = None):
        """
        Ramps the voltage on all channels in the GateSet to zero.
        Also resets the integrated voltage for each tracker.

        Args:
            ramp_duration_ns: Optional. The duration (ns) of the ramp to zero.
                If None, QUA's `ramp_to_zero` command is used for an immediate ramp.
        """
        for ch_name, channel_obj in self.gate_set.channels.items():
            tracker = self.state_trackers[ch_name]

            if ramp_duration_ns is None:
                ramp_to_zero(channel_obj.name)
            else:
                self._perform_ramp_to_zero_with_duration(
                    channel_obj, tracker, ramp_duration_ns
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
