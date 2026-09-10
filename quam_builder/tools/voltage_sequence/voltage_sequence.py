from typing import Dict, Optional, Tuple
from contextlib import contextmanager

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
    align,
)
from qm.qua._scope_management.scopes_manager import scopes_manager
from qm.qua.type_hints import QuaVariable, QuaScalarExpression

from quam.components.channels import SingleChannel
from quam.components.pulses import SquarePulse
from quam.components import pulses

from quam_builder.architecture.quantum_dots.components.gate_set import (
    GateSet,
    VoltageTuningPoint,
)
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS

from .sequence_state_tracker import (
    SequenceStateTracker,
    INTEGRATED_VOLTAGE_SCALING_FACTOR,
    KeepLevels,
)
from .exceptions import VoltagePointError
from ...tools.qua_tools import (
    is_qua_type,
    integer_abs,
    validate_duration,
    VoltageLevelType,
    DurationType,
)

__all__ = [
    "VoltageTuningPoint",
    "VoltageSequence",
    "DEFAULT_PULSE_NAME",
    "MIN_PULSE_DURATION_NS",
]

MIN_PULSE_DURATION_NS = 16
CLOCK_CYCLE_NS = 4
COMPENSATION_SCALING_FACTOR = 1.0 / INTEGRATED_VOLTAGE_SCALING_FACTOR
MIN_COMPENSATION_DURATION_NS = 16
DEFAULT_QUA_COMPENSATION_DURATION_NS = 48
DEFAULT_PULSE_NAME = "half_max_square"
VOLTAGE_BITSHIFT = 12
ATTENUATION_BITSHIFT = 8
# A constant waveform at the full-scale rail is emitted one DAC code low, so a
# full-scale waveform sample plays as full_scale * DAC_RAIL_FRACTION.
DAC_RAIL_FRACTION = 32767 / 32768


def round_amplitude(level):
    """Round a voltage to 16-bit (sticky DAC / float16) precision."""
    if is_qua_type(level):
        return (level >> VOLTAGE_BITSHIFT) << VOLTAGE_BITSHIFT
    return float(np.float16(level))


def _channel_full_scale(channel) -> float:
    if hasattr(channel, "full_scale"):
        return float(channel.full_scale)
    opx = getattr(channel, "opx_output", None)
    if opx is not None and getattr(opx, "output_mode", None) == "amplified":
        return 2.5
    return 0.5


def _channel_wf_amp(channel) -> float:
    if DEFAULT_PULSE_NAME in getattr(channel, "operations", {}):
        return float(channel.operations[DEFAULT_PULSE_NAME].amplitude)
    return _channel_full_scale(channel)


def _device_to_opx(channel, voltage, adjust: bool):
    if not adjust:
        return voltage
    if hasattr(channel, "device_to_opx"):
        return channel.device_to_opx(voltage)
    att = getattr(channel, "attenuation", 0.0) or 0.0
    return voltage * (10 ** (att / 20))


def _amplitude_scale(delta_opx, wf_amp: float):
    inv = 1.0 / wf_amp
    log2_inv = np.log2(inv)
    if is_qua_type(delta_opx):
        if log2_inv == int(log2_inv) and int(log2_inv) >= 0:
            return delta_opx << int(log2_inv)
        return delta_opx * inv
    return float(np.clip(float(delta_opx) * inv, -2.0, 2.0))


def _correct_for_dac_rail(delta_v):
    """Ask for the delta the DAC has to reach to land on the requested voltage.

    Only applies to Python deltas; QUA deltas keep the cheaper bit-shift scaling.
    """
    if is_qua_type(delta_v):
        return delta_v
    return float(delta_v) / DAC_RAIL_FRACTION


class VoltageSequence:
    """
    Manages the generation of a QUA sequence for setting and adjusting DC voltages
    on a set of gate channels defined within a GateSet.
    """

    def __init__(
        self,
        gate_set: GateSet,
        track_integrated_voltage: bool = True,
        keep_levels: bool = True,
        enforce_qua_calcs: bool = True,
        limit_play_commands: bool = False,
    ):
        self.gate_set: GateSet = gate_set
        self._update_baseband_pulse_amplitude()
        self.state_trackers: Dict[str, SequenceStateTracker] = {
            ch_name: SequenceStateTracker(
                ch_name,
                track_integrated_voltage=track_integrated_voltage,
                enforce_qua_calcs=enforce_qua_calcs,
            )
            for ch_name in self.gate_set.channels.keys()
        }
        self._temp_qua_vars: Dict[str, QuaVariable] = {}
        self._track_integrated_voltage: bool = track_integrated_voltage
        self._keep_levels: bool = keep_levels
        self._enforce_qua_calcs: bool = enforce_qua_calcs
        self._channel_max_voltage: Dict[str, float] = {}

        for ch_name, channel_obj in self.gate_set.channels.items():
            self._ensure_default_pulse(channel_obj)
            opx_voltage_limit = _channel_full_scale(channel_obj)
            if self.gate_set.adjust_for_attenuation and hasattr(channel_obj, "attenuation"):
                attenuation_scale = 10 ** (channel_obj.attenuation / 20)
                self._channel_max_voltage[ch_name] = opx_voltage_limit / attenuation_scale
            else:
                self._channel_max_voltage[ch_name] = opx_voltage_limit

        if self._keep_levels:
            self._keep_levels_tracker = KeepLevels(self.gate_set)

        self._batched_voltages = None
        self._prog_id = None
        self.limit_play_commands: bool = limit_play_commands

        try:
            if scopes_manager.program_scope is not None:
                self.declare_qua_variables()
                self._prog_id = id(scopes_manager.program_scope)
                if self.gate_set.adjust_for_attenuation:
                    self._initialise_attenuation_qua_vars()
        except Exception:
            pass

    def _ensure_default_pulse(self, channel_obj: SingleChannel) -> None:
        if DEFAULT_PULSE_NAME in channel_obj.operations:
            return
        amplitude = _channel_full_scale(channel_obj)
        channel_obj.operations[DEFAULT_PULSE_NAME] = pulses.SquarePulse(
            amplitude=amplitude, length=MIN_PULSE_DURATION_NS
        )

    def _check_for_new_program(self, update_prog_id: bool = False) -> bool:
        current_program_scope = id(scopes_manager.program_scope)
        is_new = self._prog_id != current_program_scope
        if update_prog_id:
            self._prog_id = current_program_scope
        return is_new

    def _update_baseband_pulse_amplitude(self):
        for ch in self.gate_set.channels.values():
            if ch.opx_output is not None:
                amp = _channel_full_scale(ch)
                if DEFAULT_PULSE_NAME not in ch.operations:
                    ch.operations[DEFAULT_PULSE_NAME] = SquarePulse(
                        id=DEFAULT_PULSE_NAME,
                        length=MIN_PULSE_DURATION_NS,
                        amplitude=amp,
                    )
                else:
                    ch.operations[DEFAULT_PULSE_NAME].amplitude = amp

    def _initialise_attenuation_qua_vars(self) -> None:
        self.attenuation_qua_variables = {
            ch_name: (
                declare(
                    fixed,
                    value=10 ** (ch.attenuation / 20) / (1 << ATTENUATION_BITSHIFT),
                )
                if hasattr(ch, "attenuation")
                else declare(fixed, value=1 / (1 << ATTENUATION_BITSHIFT))
            )
            for (ch_name, ch) in self.gate_set.channels.items()
        }
        if self.gate_set.adjust_for_attenuation:
            self._attenuated_delta_v_vars: Dict[str, QuaVariable] = {
                ch_name: declare(fixed) for ch_name in self.gate_set.channels.keys()
            }

    def declare_qua_variables(self):
        for tracker in self.state_trackers.values():
            tracker.initialize_qua_vars()

    @contextmanager
    def simultaneous(self, duration: int = 16, ramp_duration: int = None):
        self._batched_voltages = {}
        try:
            yield
        finally:
            if self._batched_voltages:
                voltages_to_execute = self._batched_voltages.copy()
                self._batched_voltages = None
                if ramp_duration == 0 or ramp_duration is None:
                    self.step_to_voltages(voltages_to_execute, duration)
                else:
                    self.ramp_to_voltages(voltages_to_execute, ramp_duration, duration)
            else:
                self._batched_voltages = None

    def _get_temp_qua_var(self, name_suffix: str, var_type=fixed) -> QuaVariable:
        internal_name = f"_vseq_tmp_{name_suffix}"
        if internal_name not in self._temp_qua_vars:
            self._temp_qua_vars[internal_name] = declare(var_type)
        return self._temp_qua_vars[internal_name]

    def _adjust_for_attenuation(self, channel, delta_v):
        att = getattr(channel, "attenuation", 0.0) or 0.0
        if att == 0.0:
            return delta_v
        ch_name = next(name for name, ch in self.gate_set.channels.items() if ch is channel)
        attenuation_scale = self.attenuation_qua_variables[ch_name]
        if is_qua_type(delta_v):
            unattenuated_delta_v = self._attenuated_delta_v_vars[ch_name]
            assign(
                unattenuated_delta_v,
                (delta_v * attenuation_scale) << ATTENUATION_BITSHIFT,
            )
            return unattenuated_delta_v
        return delta_v * (10 ** (att / 20))

    def _assign_step_amplitude_scale(self, channel, delta_v, scale_var):
        if self.gate_set.adjust_for_attenuation:
            delta_v = self._adjust_for_attenuation(channel, delta_v)
        wf = _channel_wf_amp(channel)
        assign(scale_var, _amplitude_scale(_correct_for_dac_rail(delta_v), wf))

    def _play_step_on_channel(self, channel, delta_v, duration):
        wf = _channel_wf_amp(channel)
        if self.gate_set.adjust_for_attenuation:
            delta_v = self._adjust_for_attenuation(channel, delta_v)

        py_duration = 0
        if not is_qua_type(duration):
            py_duration = int(float(str(duration)))
        if py_duration == 0 and not is_qua_type(duration):
            return

        scaled_amp = _amplitude_scale(_correct_for_dac_rail(delta_v), wf)
        duration_cycles = duration >> 2
        channel.play(
            DEFAULT_PULSE_NAME,
            amplitude_scale=scaled_amp,
            duration=duration_cycles if is_qua_type(duration) else py_duration >> 2,
            validate=False,
        )

    def _play_ramp_on_channel(self, channel, delta_v, ramp_duration, hold_duration):
        if self.gate_set.adjust_for_attenuation:
            delta_v = self._adjust_for_attenuation(channel, delta_v)
        py_ramp_duration = 0
        if not is_qua_type(ramp_duration):
            py_ramp_duration = int(float(str(ramp_duration)))

        ramp_duration_cycles = (
            ramp_duration >> 2 if is_qua_type(ramp_duration) else py_ramp_duration >> 2
        )

        if is_qua_type(delta_v) or is_qua_type(ramp_duration):
            ramp_rate = self._get_temp_qua_var(f"{channel.name}_ramp_rate")
            if not is_qua_type(ramp_duration) and py_ramp_duration > 0:
                assign(ramp_rate, delta_v * (1.0 / py_ramp_duration))
            else:
                inv_ramp_dur = self._get_temp_qua_var(f"{channel.name}_inv_ramp_dur", fixed)
                assign(inv_ramp_dur, Math.div(1, ramp_duration))
                assign(ramp_rate, delta_v * inv_ramp_dur)
            channel.play(ramp(ramp_rate), duration=ramp_duration_cycles, validate=False)
        else:
            py_delta_v = float(str(delta_v))
            if py_ramp_duration > 0:
                channel.play(
                    ramp(py_delta_v / py_ramp_duration),
                    duration=ramp_duration_cycles,
                    validate=False,
                )

        py_hold_duration = 0
        if not is_qua_type(hold_duration):
            py_hold_duration = int(float(str(hold_duration)))

        if is_qua_type(hold_duration):
            wait_cycles = hold_duration >> 2
            with if_(wait_cycles > 0):
                channel.wait(wait_cycles)
        elif py_hold_duration > 0:
            channel.wait(py_hold_duration >> 2)

    def _common_voltages_change(  # pylint: disable=too-many-statements
        self,
        target_voltages_dict: Dict[str, VoltageLevelType],
        duration: DurationType,
        ramp_duration: Optional[DurationType] = None,
        ensure_align: bool = True,
    ):
        if self._check_for_new_program(update_prog_id=True):
            self._temp_qua_vars.clear()
            self.declare_qua_variables()
            if self.gate_set.adjust_for_attenuation:
                self._initialise_attenuation_qua_vars()

        if self._batched_voltages is not None:
            self._batched_voltages.update(target_voltages_dict)
            return

        validate_duration(duration, "duration")
        if ramp_duration is not None:
            validate_duration(ramp_duration, "ramp_duration")

        changed_gates = set(target_voltages_dict.keys())
        if self._keep_levels:
            target_voltages_dict = self._keep_levels_tracker.update_voltage_dict_with_current(
                target_voltages_dict
            )

        full_target_voltages_dict = self.gate_set.resolve_voltages(target_voltages_dict)
        if hasattr(self.gate_set, "influence_map") and self.limit_play_commands:
            affected = set()
            for gate in changed_gates:
                affected = affected | self.gate_set.influence_map.get(gate, {gate})
            full_target_voltages_dict = {
                ch: v for ch, v in full_target_voltages_dict.items() if ch in affected
            }
        else:
            affected = set(full_target_voltages_dict)

        if ensure_align:
            align(*full_target_voltages_dict)

        pending = []
        for ch_name, target_voltage in full_target_voltages_dict.items():
            if ch_name not in self.gate_set.channels:
                continue
            if isinstance(target_voltage, int):
                target_voltage = float(target_voltage)
            target_voltage = round_amplitude(target_voltage)
            tracker = self.state_trackers[ch_name]
            channel_obj = self.gate_set.channels[ch_name]
            current_v = tracker.current_level

            if is_qua_type(target_voltage):
                delta_v = target_voltage - current_v
            elif is_qua_type(current_v):
                delta_v = float(str(target_voltage)) - tracker._python_level
            else:
                delta_v = float(str(target_voltage)) - float(str(current_v))

            if self._track_integrated_voltage:
                tracker.update_integrated_voltage(target_voltage, duration, ramp_duration)

            pending.append((ch_name, channel_obj, tracker, target_voltage, delta_v))

        for ch_name, channel_obj, tracker, target_voltage, delta_v in pending:
            if not is_qua_type(delta_v) and delta_v == 0.0:
                tracker.current_level = target_voltage
                continue
            if ramp_duration is None or (
                not is_qua_type(ramp_duration) and int(float(str(ramp_duration))) == 0
            ):
                self._play_step_on_channel(channel_obj, delta_v, duration)
            else:
                self._play_ramp_on_channel(channel_obj, delta_v, ramp_duration, duration)
            tracker.current_level = target_voltage

        if (
            self._track_integrated_voltage
            and hasattr(self.gate_set, "influence_map")
            and self.limit_play_commands
        ):
            for ch_name in self.gate_set.channels:
                if ch_name not in affected:
                    tracker = self.state_trackers[ch_name]
                    tracker.update_integrated_voltage(tracker.current_level, duration, None)

    def step_to_voltages(
        self,
        voltages: Dict[str, VoltageLevelType],
        duration: DurationType,
        ensure_align: bool = True,
    ):
        self._common_voltages_change(
            voltages, duration, ramp_duration=None, ensure_align=ensure_align
        )

    def ramp_to_voltages(
        self,
        voltages: Dict[str, VoltageLevelType],
        duration: DurationType,
        ramp_duration: DurationType,
        ensure_align: bool = True,
    ):
        self._common_voltages_change(
            voltages, duration, ramp_duration=ramp_duration, ensure_align=ensure_align
        )

    def track_sticky_duration(self, duration_ns: int) -> None:
        if not self._track_integrated_voltage:
            return
        if not isinstance(duration_ns, int):
            raise TypeError("duration_ns must be an integer number of nanoseconds.")
        if duration_ns < 0:
            raise TypeError("duration_ns must be non-negative.")
        if duration_ns % CLOCK_CYCLE_NS != 0:
            raise TypeError(
                f"duration_ns ({duration_ns}ns) must be a multiple of {CLOCK_CYCLE_NS}ns."
            )
        if duration_ns == 0:
            return
        for tracker in self.state_trackers.values():
            tracker.update_integrated_voltage(
                level=tracker.current_level,
                duration=duration_ns,
                ramp_duration=None,
            )

    def step_to_point(
        self,
        name: str,
        duration: Optional[DurationType] = None,
        ensure_align: bool = True,
    ):
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
            ramp_duration=None,
            ensure_align=ensure_align,
        )

    def ramp_to_point(
        self,
        name: str,
        ramp_duration: DurationType,
        duration: Optional[DurationType] = None,
        ensure_align: bool = True,
    ):
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
            ensure_align=ensure_align,
        )

    def _calculate_python_compensation_params(
        self,
        tracker: SequenceStateTracker,
        max_voltage: float,
    ) -> Tuple[float, int]:
        area = tracker.python_area_v_ns()
        if area == 0.0:
            return 0.0, 0
        ideal_dur = abs(area / max_voltage)
        py_comp_dur = max(ideal_dur, MIN_COMPENSATION_DURATION_NS)
        py_comp_dur = (
            (int(np.ceil(py_comp_dur)) + CLOCK_CYCLE_NS - 1) // CLOCK_CYCLE_NS * CLOCK_CYCLE_NS
        )
        py_comp_dur = max(py_comp_dur, DEFAULT_QUA_COMPENSATION_DURATION_NS)
        py_comp_amp = -(area) / py_comp_dur if py_comp_dur > 0 else 0.0
        py_comp_amp = float(np.clip(py_comp_amp, -max_voltage, max_voltage))
        return py_comp_amp, py_comp_dur

    def _calculate_qua_compensation_params(
        self,
        tracker: SequenceStateTracker,
        max_voltage: float,
        channel_id_str: str,
    ) -> Tuple[QuaScalarExpression, QuaScalarExpression]:
        """Duration and amplitude from the full scaled area (not truncated V·ns)."""
        integrated_v = tracker.integrated_voltage

        signed_int_v = self._get_temp_qua_var(f"{channel_id_str}_eval_int_v", int)
        abs_int_v = self._get_temp_qua_var(f"{channel_id_str}_abs_int", int)
        q_comp_dur = self._get_temp_qua_var(f"{channel_id_str}_comp_dur", int)
        q_comp_amp_scaled = self._get_temp_qua_var(f"{channel_id_str}_comp_amp_scaled", int)
        q_comp_amp = self._get_temp_qua_var(f"{channel_id_str}_comp_amp", fixed)
        inv_dur = self._get_temp_qua_var(f"{channel_id_str}_inv_dur", fixed)

        assign(signed_int_v, integrated_v)
        assign(abs_int_v, integrated_v)
        abs_int_v = integer_abs(abs_int_v)

        assign(
            q_comp_dur,
            Cast.mul_int_by_fixed(abs_int_v, COMPENSATION_SCALING_FACTOR / max_voltage),
        )
        assign(q_comp_dur, ((q_comp_dur >> 2) + 1) << 2)
        with if_(q_comp_dur < MIN_COMPENSATION_DURATION_NS):
            assign(q_comp_dur, MIN_COMPENSATION_DURATION_NS)
        with if_(q_comp_dur < DEFAULT_QUA_COMPENSATION_DURATION_NS):
            assign(q_comp_dur, DEFAULT_QUA_COMPENSATION_DURATION_NS)

        assign(inv_dur, Math.div(1, q_comp_dur))
        assign(
            q_comp_amp_scaled,
            Cast.mul_int_by_fixed(abs_int_v + (q_comp_dur >> 1), inv_dur),
        )
        with if_(q_comp_amp_scaled == 0):
            assign(q_comp_dur, 0)
        with if_(signed_int_v > 0):
            assign(q_comp_amp_scaled, -q_comp_amp_scaled)
        assign(
            q_comp_amp,
            Cast.mul_fixed_by_int(COMPENSATION_SCALING_FACTOR, q_comp_amp_scaled),
        )
        return q_comp_amp, q_comp_dur

    def apply_compensation_pulse(
        self,
        max_voltage: float = 0.05,
        go_to_zero: bool = True,
        return_to_zero: bool = True,
    ):
        if not self._track_integrated_voltage:
            raise ValueError(
                "apply_compensation_pulse is not supported when integrated voltage is not tracked."
            )
        if max_voltage <= 0:
            raise ValueError("max_voltage must be positive.")

        if self._keep_levels:
            zero_dict = {name: 0.0 for name in self._keep_levels_tracker._keep_levels_dict}
        else:
            zero_dict = {}

        if go_to_zero:
            self._common_voltages_change(target_voltages_dict=zero_dict, duration=16)

        for ch_name, channel_obj in self.gate_set.channels.items():
            channel_limit = self._channel_max_voltage[ch_name]
            channel_max_voltage = min(max_voltage, channel_limit)
            tracker = self.state_trackers[ch_name]
            current_v = tracker.current_level
            python_area = tracker._qua_coarse is None and not is_qua_type(tracker.current_level)

            if python_area:
                py_comp_amp, py_comp_dur = self._calculate_python_compensation_params(
                    tracker, channel_max_voltage
                )
                if py_comp_dur == 0:
                    tracker.current_level = py_comp_amp
                    continue
                delta_v = py_comp_amp - float(str(current_v))
                self._play_step_on_channel(channel_obj, delta_v, py_comp_dur)
                if return_to_zero:
                    self._play_step_on_channel(channel_obj, -py_comp_amp, MIN_PULSE_DURATION_NS)
                tracker.current_level = 0.0 if return_to_zero else py_comp_amp
            else:
                q_comp_amp, q_comp_dur = self._calculate_qua_compensation_params(
                    tracker, channel_max_voltage, channel_obj.name
                )
                amp_scale_in = self._get_temp_qua_var(f"{channel_obj.name}_comp_scale_in", fixed)
                amp_scale_out = self._get_temp_qua_var(f"{channel_obj.name}_comp_scale_out", fixed)
                self._assign_step_amplitude_scale(channel_obj, q_comp_amp - current_v, amp_scale_in)
                self._assign_step_amplitude_scale(channel_obj, -q_comp_amp, amp_scale_out)
                min_cycles = channel_obj.operations[DEFAULT_PULSE_NAME].length // CLOCK_CYCLE_NS
                with if_(q_comp_dur > 0):
                    channel_obj.play(
                        DEFAULT_PULSE_NAME,
                        amplitude_scale=amp_scale_in,
                        duration=q_comp_dur >> 2,
                        validate=False,
                    )
                    if return_to_zero:
                        channel_obj.play(
                            DEFAULT_PULSE_NAME,
                            amplitude_scale=amp_scale_out,
                            duration=min_cycles,
                            validate=False,
                        )
                with else_():
                    channel_obj.play(
                        DEFAULT_PULSE_NAME,
                        amplitude_scale=amp_scale_in,
                        duration=min_cycles,
                        validate=False,
                    )
                tracker.current_level = 0.0 if return_to_zero else q_comp_amp

        if return_to_zero:
            if self._keep_levels:
                self._keep_levels_tracker.update_tracking(zero_dict)
            self.ramp_to_zero()

        for tracker in self.state_trackers.values():
            tracker.reset_integrated_voltage()

    def _perform_ramp_to_zero_with_duration(
        self,
        channel_obj: SingleChannel,
        tracker: SequenceStateTracker,
        ramp_duration: int,
    ):
        current_v = tracker.current_level
        validate_duration(ramp_duration, "ramp_duration")
        wf = _channel_wf_amp(channel_obj)
        if is_qua_type(current_v):
            ramp_rate = self._get_temp_qua_var(f"{channel_obj.name}_r2z_rate")
            with if_(ramp_duration > 0):
                inv_dur = self._get_temp_qua_var(f"{channel_obj.id}_inv_dur", fixed)
                assign(inv_dur, Math.div(1, ramp_duration))
                assign(ramp_rate, -current_v * inv_dur)
                channel_obj.play(ramp(ramp_rate), duration=ramp_duration >> 2)
            with else_():
                channel_obj.play(
                    DEFAULT_PULSE_NAME,
                    amplitude_scale=-current_v * np.round(1.0 / wf, 10),
                    duration=ramp_duration >> 2,
                    validate=False,
                )
        else:
            py_curr_v = float(str(current_v))
            if ramp_duration > 0 and py_curr_v != 0.0:
                channel_obj.play(
                    ramp(-py_curr_v / ramp_duration),
                    duration=ramp_duration >> 2,
                    validate=False,
                )
            elif py_curr_v != 0.0:
                self._play_step_on_channel(channel_obj, -py_curr_v, ramp_duration)

    def ramp_to_zero(
        self, ramp_duration: Optional[int] = None, reset_tracker: Optional[bool] = False
    ):
        if ramp_duration is None:
            if self.gate_set.adjust_for_attenuation:
                sticky_durations = [
                    int(sticky.duration)
                    for sticky in (
                        getattr(ch, "sticky", None) for ch in self.gate_set.channels.values()
                    )
                    if sticky is not None and getattr(sticky, "duration", None) is not None
                ]
                ramp_ns = max(sticky_durations) if sticky_durations else MIN_PULSE_DURATION_NS
                self.ramp_to_voltages(
                    voltages={ch_name: 0.0 for ch_name in self.gate_set.channels},
                    duration=0,
                    ramp_duration=ramp_ns,
                )
            else:
                for ch_name, channel_obj in self.gate_set.channels.items():
                    tracker = self.state_trackers[ch_name]
                    ramp_to_zero(channel_obj.name)
                    tracker.update_integrated_voltage(
                        level=0.0,
                        duration=0,
                        ramp_duration=getattr(
                            getattr(channel_obj, "sticky", None), "duration", None
                        )
                        or 0,
                    )
        else:
            self.ramp_to_voltages(
                voltages={ch_name: 0.0 for ch_name in self.gate_set.channels},
                duration=0,
                ramp_duration=ramp_duration,
            )

        if self._track_integrated_voltage:
            if reset_tracker:
                self.reset_integrated_voltage()

    def reset_integrated_voltage(self):
        for tracker in self.state_trackers.values():
            tracker.reset_integrated_voltage()

    def apply_to_config(self, config: dict):
        return
