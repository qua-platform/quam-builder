"""Voltage-balanced state macros for quantum-dot pair components.

These macros are designed for wiring onto ``QuantumDotPair`` via
:class:`VoltageBalancedMacroCatalog`. Every macro is constructed so its
net integrated voltage on every gate channel is zero, and the sequence
starts and ends at 0 V.

Assumptions
-----------
* The ``initialize`` voltage point is defined at 0 V on every channel
  (it is the rest state, not a travelled-to location).
* The ``empty`` and ``measure`` voltage points hold the positive-polarity
  target voltages; their negative-polarity counterparts are derived by
  negating the stored ``VoltageTuningPoint`` entries at runtime.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from numpy import False_
from qm import qua
from quam.core import quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    _owner_component,
    _pulse_length_samples_to_ns,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    TwoQubitMacroName,
    VoltagePointName,
)
from qualang_tools.units import unit
u = unit(coerce_to_integer=True)

__all__ = [
    "BalancedInitializeMacro",
    "BalancedEmptyMacro",
    "BalancedMeasurePSBPairMacro",
    "BalancedSensorDotMeasureMacro",
    "TwoStageBalancedInitializeMacro",
    "BalancedInitializeMacroWithConditionalDrive",
]


def _default_target_qubit_name(
    owner: Any,
    qubit_role: Optional[Literal["target", "control"]] = None,
) -> Optional[str]:
    """Resolve default drive qubit name from the owner's associated qubit pair."""
    qubit_pair = _resolve_qubit_pair_for_owner(owner)
    if qubit_pair is not None:
        role = "control" if qubit_role is None else qubit_role
        if role not in {"target", "control"}:
            raise ValueError(
                f"Invalid qubit_role '{role}'. Expected 'target' or 'control'."
            )
        if role == "control":
            control = getattr(qubit_pair, "qubit_control", None)
            if control is not None:
                return control.name
        target = getattr(qubit_pair, "qubit_target", None)
        if target is not None:
            return target.name
    return None


def _resolve_qubit_pair_for_owner(owner: Any):
    """Return the unique LDQubitPair associated with a macro owner.

    Heralded initialize macros are expected to be owned by ``QuantumDotPair``
    components (or directly by ``LDQubitPair`` wrappers). This helper resolves
    that relationship and guards against ambiguous matches.
    """
    if hasattr(owner, "qubit_target") and hasattr(owner, "qubit_control"):
        return owner

    machine = getattr(owner, "machine", None)
    owner_id = getattr(owner, "id", None)
    if machine is None:
        return None

    matches = []
    for qubit_pair in machine.qubit_pairs.values():
        dot_pair = getattr(qubit_pair, "quantum_dot_pair", None)
        if dot_pair is owner or (
            dot_pair is not None and getattr(dot_pair, "id", None) == owner_id
        ):
            matches.append(qubit_pair)

    if len(matches) > 1:
        raise ValueError(
            "Ambiguous QuantumDotPair->LDQubitPair mapping for owner "
            f"'{getattr(owner, 'id', owner)}'."
        )
    return matches[0] if matches else None


def _default_target_state(owner: Any) -> Optional[int]:
    """Resolve heralded-target-state default from the associated qubit pair."""
    qubit_pair = _resolve_qubit_pair_for_owner(owner)
    if qubit_pair is None:
        return None
    return getattr(qubit_pair, "heralded_initialize_target_state", None)


def _point_voltages(owner: Any, point: str | dict) -> dict[str, float]:
    if isinstance(point, dict):
        return point

    full_name = owner._create_point_name(point)

    tuning_point = owner.voltage_sequence.gate_set.macros.get(full_name)

    return dict(tuning_point.voltages)


def _zero_voltages(owner: Any) -> dict[str, float]:
    return {name: 0.0 for name in owner.voltage_sequence.gate_set.valid_channel_names}


@quam_dataclass
class _BalancedRoundTripMacro(QuamMacro):
    """Balanced round-trip: ramp 0 → -V → +V → 0 through a named voltage point.

    Shape (per channel):

        0  ──ramp──▶  -V  ──hold──  -V  ──ramp──▶  +V  ──hold──  +V  ──ramp──▶  0

    Ramp 1 and ramp 3 are mirror triangles of each other; ramp 2 is
    antisymmetric about 0 V and integrates to zero. The two holds are
    equal, so their +V and -V contributions cancel. Net integrated
    voltage: zero on every channel.

    Ramp 2 covers twice the voltage of ramps 1 and 3, so its duration is
    ``2 * ramp_duration`` to preserve the same slope (consistent dV/dt).
    """

    point: str = VoltagePointName.EMPTY.value
    ramp_duration: int = DEFAULTS.state_macro.ramp_duration
    hold_duration: int = DEFAULTS.state_macro.hold_duration

    @property
    def inferred_duration(self) -> float | None:
        return (2 * self.ramp_duration + 2 * self.hold_duration + 16) * 1e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        ramp_duration: int | None = None,
        hold_duration: int | None = None,
        point: str | dict | None = None,
        **kwargs,
    ):
        owner = _owner_component(self)
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        hold = self.hold_duration if hold_duration is None else hold_duration
        target_point = self.point if point is None else point

        positive = _point_voltages(owner, target_point)
        negative = {k: -v for k, v in positive.items()}
        zero = {k: 0.0 for k, _ in positive.items()}
        vs = owner.voltage_sequence
        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]
        qua.align(*gates)

        # with qua.strict_timing_():
        vs.ramp_to_voltages(
            negative,
            duration=hold,
            ramp_duration=ramp,
            ensure_align=False,
        )
        vs.ramp_to_voltages(
            positive,
            duration=hold,
            ramp_duration=2*ramp,
            ensure_align=False,
        )
        vs.ramp_to_voltages(
            zero,
            duration=DEFAULTS.state_macro.point_duration,
            ramp_duration=ramp,
            ensure_align=False,
        )

    def update(
        self,
        *,
        ramp_duration: int | None = None,
        hold_duration: int | None = None,
        point: str | None = None,
    ) -> None:
        if ramp_duration is not None:
            self.ramp_duration = ramp_duration
        if hold_duration is not None:
            self.hold_duration = hold_duration
        if point is not None:
            self.point = point


@quam_dataclass
class BalancedInitializeMacro(_BalancedRoundTripMacro):
    """Voltage-balanced initialize: ramp 0 → -empty → +empty → 0."""

    point: str = VoltagePointName.INITIALIZE.value

@quam_dataclass
class BalancedHeraldedInitializeMacro(BalancedInitializeMacro): 
    def apply(
            self,
            max_loops: int = 2,
            target_state: Optional[Literal[0, 1]] = None,
            return_n_loops: bool = False,
            conditional_drive: bool = True,
            operation: str = "x180",
            qubit_role: Optional[Literal["target", "control"]] = None,
            qubit_name: Optional[str] = None,
            meas_ramp_duration: Optional[int] = None,
            meas_buffer_duration: Optional[int] = None,
            **kwargs
        ):
        owner = _owner_component(self)
        if qubit_name is None:
            qubit_name = _default_target_qubit_name(owner, qubit_role=qubit_role)
            if qubit_name is None:
                raise ValueError(
                    "Heralded initialize: no `qubit_name` given and could not "
                    f"resolve a default target qubit for pair '{getattr(owner, 'id', owner)}'."
                )
        if target_state is None:
            target_state = _default_target_state(owner)
        if target_state is None:
            target_state = 0
        loop_start_n, loop_start_bool = 0, True

        n_count = qua.declare(int)
        qua.assign(n_count, loop_start_n)

        cond = qua.declare(bool)
        qua.assign(cond, loop_start_bool)

        with qua.while_((cond) & (n_count < max_loops)):
            # First initialise. super() should be BalancedInitializeMacro
            super().apply(**kwargs)

            # Now measure the state
            state = owner.measure(
                return_iq=False,
                ramp_duration=meas_ramp_duration,
                buffer_duration=meas_buffer_duration,
            )

            # As long as the state is in the initial value, the loop will continue until max_loops
            #qua.assign(cond, qua.Cast.to_bool(state - target_state))
            qua.assign(n_count, n_count + 1)
            qubit = owner.machine.qubits[qubit_name]
            with qua.if_(cond):
                qubit.apply(operation)

        if return_n_loops: 
            return n_count
        return None


@quam_dataclass
class BalancedHeraldedInitializeMacroWithMemory(BalancedInitializeMacro): 
    def apply(
            self,
            max_loops: int = 1000,
            target_state: Optional[Literal[0, 1]] = None,
            return_n_loops: bool = False,
            conditional_drive: bool = True,
            operation: str = "x180",
            qubit_role: Optional[Literal["target", "control"]] = None,
            qubit_name: Optional[str] = None,
            meas_ramp_duration: Optional[int] = None,
            meas_buffer_duration: Optional[int] = None,
            **kwargs
        ):
        owner = _owner_component(self)
        if qubit_name is None:
            qubit_name = _default_target_qubit_name(owner, qubit_role=qubit_role)
            if qubit_name is None:
                raise ValueError(
                    "Heralded initialize (memory): no `qubit_name` given and could "
                    f"not resolve a default target qubit for pair '{getattr(owner, 'id', owner)}'."
                )
        if target_state is None:
            target_state = _default_target_state(owner)
        if target_state is None:
            target_state = 1
        loop_start_n, loop_start_bool = 0, True

        n_count = qua.declare(int)
        qua.assign(n_count, loop_start_n)

        cond = qua.declare(bool)
        qua.assign(cond, loop_start_bool)

        prev_cond = qua.declare(bool)
        qua.assign(prev_cond, False)

        drive_success = qua.declare(bool)
        qua.assign(drive_success, False)

        # FIRST LOOP: We always initialise, measure, drive. 

        # First INIT
        super().apply(**kwargs)
        # First MEASURE
        prev_state = owner.measure(
            return_iq=False,
            ramp_duration=meas_ramp_duration,
            buffer_duration=meas_buffer_duration,
        )

        qua.assign(prev_cond, prev_state)
        # First DRIVE
        qubit = owner.machine.qubits[qubit_name]
        qubit.apply(operation)

        # qua.assign(prev_cond, qua.Cast.to_bool(prev_state - target_state))

        # Now, we enter the loop. In this loop, we initialise, measure, and conditionally drive. 
        # The drive condition: 
            # - Regardless of whether the prev_cond is FALSE (target) or TRUE (non-target), if the loop measures 
            #   the OPPOSITE condition, then this means that the drive worked. We therefore drive if the state is NOT 
            #   at the target state. Easy. 
            # - If the newly measured state is the SAME condition, this means that the drive did not work, and that we are stuck. 
            #   In this case, we will continue the loop until we measure the opposite state, and then exit, conditionally driving. 


        with qua.while_((n_count < max_loops) & (cond | ~drive_success)):
            # First initialise. super() should be BalancedInitializeMacro
            super().apply(**kwargs)

            # Now measure the state
            state = owner.measure(
                return_iq=False,
                ramp_duration=meas_ramp_duration,
                buffer_duration=meas_buffer_duration,
            )

            # As long as the state is in the initial value, the loop will continue until max_loops
            qua.assign(cond, qua.Cast.to_bool(state - target_state))

            # If cond != prev_cond, then drive worked. 
            with qua.if_(state ^ prev_cond): # IF DIFFERENT, THEN TRUE. 
                qua.assign(drive_success, True)
            
            # IF SAME, THEN FALSE, drive_success = FALSE. 
            
            qua.assign(n_count, n_count + 1)
            qubit = owner.machine.qubits[qubit_name]
            with qua.if_(cond):
                qubit.apply(operation)

            qua.assign(prev_cond, state)

        if return_n_loops: 
            return n_count
        return None

@quam_dataclass
class BalancedEmptyMacro(_BalancedRoundTripMacro):
    """Voltage-balanced empty: ramp 0 → -empty → +empty → 0.

    Shares the round-trip shape with :class:`BalancedInitializeMacro`;
    kept as a separate class so ``empty`` remains an independently-
    configurable balanced operation.
    """

    point: str = VoltagePointName.EMPTY.value

    def apply(
        self,
        measure_and_conditional_drive: bool = False,
        state: Literal["less_than_one", "more_than_zero"] = "less_than_one",
        drive_at_readout_point: bool = True,
        pulse_name: str = "x180",
        amplitude_scale: float = 1.0,
        frequency_detuning_Hz: int = 0,
        ramp_duration: int | None = None,
        buffer_duration: int = 0,
        hold_duration: int | None = None,
        drive_point: str | dict | None = None,
        point: str | dict | None = None,
        **kwargs,
    ):
        owner = _owner_component(self)
        vs = owner.voltage_sequence
        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        hold = self.hold_duration if hold_duration is None else hold_duration
        operation_point = self.point if point is None else point

        if not measure_and_conditional_drive:
            return super().apply(
                ramp_duration=ramp,
                hold_duration=hold,
                point=operation_point,
                **kwargs,
            )

        pulse = f"{owner.machine.pulse_family}_{pulse_name}"
        try:
            qubit_pair = [
                qp
                for qp in owner.machine.qubit_pairs.values()
                if qp.quantum_dot_pair.name == owner.name
            ][0]
        except IndexError as exc:
            raise ValueError(f"Qubit Pair not found for {owner.name}.") from exc

        xy_channel = qubit_pair.xy
        xy_channel.update_frequency(xy_channel.intermediate_frequency + frequency_detuning_Hz)
        op_length = xy_channel.operations[pulse].length

        def _conditional_drive(result_int):
            if state == "less_than_one":
                with qua.if_(result_int < 1):
                    xy_channel.play(pulse, amplitude_scale=amplitude_scale)
                with qua.else_():
                    qua.wait(op_length // 4, xy_channel.name)
            else:
                with qua.if_(result_int > 0):
                    xy_channel.play(pulse, amplitude_scale=amplitude_scale)
                with qua.else_():
                    qua.wait(op_length // 4, xy_channel.name)

        if not drive_at_readout_point:
            qua.align(xy_channel.id, owner.sensor_dots[0].readout_resonator.id, *gates)
            result = owner.measure(return_iq=False)
            result_int = qua.Cast.to_int(result)
            qua.align(xy_channel.id, owner.sensor_dots[0].readout_resonator.id, *gates)
            _conditional_drive(result_int)
            qua.align(xy_channel.id, owner.sensor_dots[0].readout_resonator.id, *gates)
            return result

        if not owner.sensor_dots:
            raise ValueError(f"QuantumDotPair '{owner.name}' has no sensor dots for readout")

        sensor_dot = owner.sensor_dots[0]
        sensor_macro = sensor_dot.macros[TwoQubitMacroName.MEASURE]
        if hasattr(sensor_macro, "readout_pulse_length_ns_for_pair"):
            readout_len = sensor_macro.readout_pulse_length_ns_for_pair(owner.id)
        else:
            readout_len = sensor_macro.readout_pulse_length_ns
        if readout_len is None:
            raise ValueError(
                "Sensor readout pulse length unknown; conditional drive requires "
                "a fixed readout duration."
            )

        measure_point = VoltagePointName.MEASURE.value
        target_drive_point = measure_point if drive_point is None else drive_point
        measure_macro = owner.macros[TwoQubitMacroName.MEASURE]
        measure_ramp_duration = getattr(measure_macro, "ramp_duration", ramp)
        measure_buffer_duration = getattr(measure_macro, "buffer_duration", buffer_duration)

        measure_positive = _point_voltages(owner, measure_point)
        measure_negative = {k: -v for k, v in measure_positive.items()}
        drive_positive = _point_voltages(owner, target_drive_point)
        drive_negative = {k: -v for k, v in drive_positive.items()}
        zero_voltages = _zero_voltages(owner)

        qua.align(sensor_dot.readout_resonator.name, xy_channel.name, *gates)

        with qua.strict_timing_():
            # 1) Ramp to negative drive point and hold for operation window.
            vs.ramp_to_voltages(
                drive_negative,
                duration=op_length + hold,
                ramp_duration=ramp,
                ensure_align=False,
            )
            qua.wait((ramp + op_length + hold) // 4, xy_channel.name)
            qua.wait((ramp + op_length + hold) // 4, sensor_dot.readout_resonator.name)

            # 2) Ramp to negative measure point, wait buffer and readout window.
            vs.ramp_to_voltages(
                measure_negative,
                duration=measure_buffer_duration + readout_len,
                ramp_duration=measure_ramp_duration,
                ensure_align=False,
            )
            qua.wait(
                (measure_ramp_duration + measure_buffer_duration + readout_len) // 4,
                xy_channel.name,
            )
            qua.wait(
                (measure_ramp_duration + measure_buffer_duration + readout_len) // 4,
                sensor_dot.readout_resonator.name,
            )

            # 3) Ramp to positive measure point, wait buffer, then measure.
            vs.ramp_to_voltages(
                measure_positive,
                duration=measure_buffer_duration + readout_len,
                ramp_duration=2 * measure_ramp_duration,
                ensure_align=False,
            )
            qua.wait(
                (2 * measure_ramp_duration + measure_buffer_duration) // 4,
                sensor_dot.readout_resonator.name,
            )

            result = sensor_macro.apply(
                quantum_dot_pair_id=owner.id,
                return_iq=False,
            )
            result_int = qua.Cast.to_int(result)
            qua.wait(
                (2 * measure_ramp_duration + measure_buffer_duration + readout_len) // 4,
                xy_channel.name,
            )

            # 4) Ramp to drive point, conditionally drive, then hold.
            vs.ramp_to_voltages(
                drive_positive,
                duration=op_length + hold,
                ramp_duration=ramp,
                ensure_align=False,
            )
            qua.wait((ramp + op_length + hold) // 4, sensor_dot.readout_resonator.name)
            qua.wait(ramp // 4, xy_channel.name)
            _conditional_drive(result_int)
            qua.wait(hold // 4, xy_channel.name)

            # 5) Ramp to zero point.
            # vs.ramp_to_voltages(
            #     zero_voltages,
            #     duration=DEFAULTS.state_macro.point_duration,
            #     ramp_duration=ramp,
            #     ensure_align=False,
            # )
            vs.ramp_to_zero(
                ramp_duration = ramp
            )

        return result


@quam_dataclass
class TwoStageBalancedInitializeMacro(QuamMacro):
    """Anti-symmetric two-stage ramp for initialization.

    Shape (per channel)::

        0 ──rd1──▶ -V2 ──rd2──▶ -V1 ──hold── -V1 ──rd_mid──▶ +V1 ──hold── +V1 ──rd2──▶ +V2 ──rd1──▶ 0

    The positive phase retraces the negative phase in reverse order,
    making the waveform anti-symmetric: ``f(t) = -f(T - t)``.  This
    guarantees the net integrated voltage is exactly zero for any
    combination of V1, V2, and ramp durations.

    ``point_1`` supplies the inner (initialization) voltages V1 and
    ``point_2`` supplies the outer voltages V2, both resolved from
    stored :class:`VoltageTuningPoint` entries.  Alternatively, callers
    can pass explicit voltage dicts (including QUA variables) via
    ``voltages_1`` / ``voltages_2`` to bypass the lookup.
    """

    point_1: str = VoltagePointName.INITIALIZE.value
    point_2: str = VoltagePointName.EMPTY.value
    ramp_duration_1: int = DEFAULTS.state_macro.ramp_duration
    ramp_duration_2: int = DEFAULTS.state_macro.ramp_duration
    ramp_duration_mid: int = 16
    hold_duration: int = DEFAULTS.state_macro.hold_duration

    @property
    def inferred_duration(self) -> float | None:
        rd1 = self.ramp_duration_1
        rd2 = self.ramp_duration_2
        rd_mid = self.ramp_duration_mid
        hold = self.hold_duration
        total_ns = (
            2 * rd1       # segments 1 + 5
            + 2 * rd2     # segments 2 + 4
            + rd_mid       # segment 3
            + 2 * hold    # holds at -V1 and +V1
            + DEFAULTS.state_macro.point_duration  # final dwell at 0
        )
        return total_ns * 1e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        ramp_duration_1: int | None = None,
        ramp_duration_2: int | None = None,
        ramp_duration_mid: int | None = None,
        hold_duration: int | None = None,
        point_1: str | None = None,
        point_2: str | None = None,
        voltages_1: dict | None = None,
        voltages_2: dict | None = None,
        **kwargs,
    ):
        owner = _owner_component(self)
        rd1 = self.ramp_duration_1 if ramp_duration_1 is None else ramp_duration_1
        rd2 = self.ramp_duration_2 if ramp_duration_2 is None else ramp_duration_2
        rd_mid = self.ramp_duration_mid if ramp_duration_mid is None else ramp_duration_mid
        hold = self.hold_duration if hold_duration is None else hold_duration

        if voltages_1 is not None:
            pos_v1 = voltages_1
        else:
            p1 = self.point_1 if point_1 is None else point_1
            pos_v1 = _point_voltages(owner, p1)

        if voltages_2 is not None:
            pos_v2 = voltages_2
        else:
            p2 = self.point_2 if point_2 is None else point_2
            pos_v2 = _point_voltages(owner, p2)

        neg_v2 = {k: -v for k, v in pos_v2.items()}
        neg_v1 = {k: -v for k, v in pos_v1.items()}
        zero = {k: 0.0 for k, _ in pos_v2.items()}

        vs = owner.voltage_sequence
        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]
        qua.align(*gates)

        # with qua.strict_timing_():
        vs.ramp_to_voltages(
            neg_v2, duration=16, ramp_duration=rd1, ensure_align=False,
        )
        vs.ramp_to_voltages(
            neg_v1, duration=hold, ramp_duration=rd2, ensure_align=False,
        )
        vs.ramp_to_voltages(
            pos_v1, duration=hold, ramp_duration=rd_mid, ensure_align=False,
        )
        vs.ramp_to_voltages(
            pos_v2, duration=16, ramp_duration=rd2, ensure_align=False,
        )
        vs.ramp_to_voltages(
            zero,
            duration=DEFAULTS.state_macro.point_duration,
            ramp_duration=rd1,
            ensure_align=False,
        )

    def update(
        self,
        *,
        ramp_duration_1: int | None = None,
        ramp_duration_2: int | None = None,
        ramp_duration_mid: int | None = None,
        hold_duration: int | None = None,
        point_1: str | None = None,
        point_2: str | None = None,
    ) -> None:
        if ramp_duration_1 is not None:
            self.ramp_duration_1 = ramp_duration_1
        if ramp_duration_2 is not None:
            self.ramp_duration_2 = ramp_duration_2
        if ramp_duration_mid is not None:
            self.ramp_duration_mid = ramp_duration_mid
        if hold_duration is not None:
            self.hold_duration = hold_duration
        if point_1 is not None:
            self.point_1 = point_1
        if point_2 is not None:
            self.point_2 = point_2


@quam_dataclass
class BalancedMeasurePSBPairMacro(QuamMacro):
    """Voltage-balanced PSB readout for a :class:`QuantumDotPair` (work in progress).

    The step order in :meth:`apply` is ramp to the measure point, readout, then
    balance ramps. Optional ``strict_timing_`` on the pre-readout ramp is
    commented in code (off by default) for assessment.

    Returns the QUA boolean from the sensor (same idea as
    :class:`MeasurePSBPairMacro`).
    """

    point: str = VoltagePointName.MEASURE.value
    ramp_duration: int = DEFAULTS.state_macro.ramp_duration
    buffer_duration: int = DEFAULTS.state_macro.buffer_duration

    @property
    def inferred_duration(self) -> float | None:
        owner = _owner_component(self)
        if not getattr(owner, "sensor_dots", None):
            return None
        sensor = owner.sensor_dots[0]
        sensor_macro = sensor.macros.get(TwoQubitMacroName.MEASURE)
        if sensor_macro is None:
            return None
        if hasattr(sensor_macro, "readout_pulse_length_ns_for_pair"):
            readout_len = sensor_macro.readout_pulse_length_ns_for_pair(owner.id)
        else:
            readout_len = sensor_macro.readout_pulse_length_ns
        if readout_len is None:
            return None
        h = self.buffer_duration + readout_len
        r = self.ramp_duration
        # Match apply(): (r+buf) + readout + (2*r+h) + (r+return_hold) ns
        return (16 + 2 * r + 2 * h + DEFAULTS.state_macro.point_duration) * 1e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        ramp_duration: int | None = None,
        buffer_duration: int | None = None,
        point: str | None = None,
        return_iq: bool = False,
        **kwargs,
    ):
        owner = _owner_component(self)
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        buf = self.buffer_duration if buffer_duration is None else buffer_duration
        target_point = self.point if point is None else point

        if not owner.sensor_dots:
            raise ValueError(f"QuantumDotPair '{owner.id}' has no sensor dots for readout.")
        sensor_dot = owner.sensor_dots[0]
        sensor_macro = sensor_dot.macros[TwoQubitMacroName.MEASURE]
        if hasattr(sensor_macro, "readout_pulse_length_ns_for_pair"):
            readout_len = sensor_macro.readout_pulse_length_ns_for_pair(owner.id)
        else:
            readout_len = sensor_macro.readout_pulse_length_ns
        if readout_len is None:
            raise ValueError(
                "Sensor readout pulse length unknown; balanced measurement "
                "requires a fixed readout duration."
            )

        hold = buf + readout_len
        # `ramp` / `buf` may be QUA variables (e.g. when scanned via input streams),
        # so avoid Python int() casting. Right-shift by 2 == integer division by 4
        # (clock cycles), and works for both Python ints and QUA int expressions.
        if isinstance(ramp, (int, float)) and isinstance(buf, (int, float)):
            wait_cycles = int((ramp + buf) // 4)
        else:
            wait_cycles = (ramp + buf) >> 2
        positive = _point_voltages(owner, target_point)
        negative = {k: -v for k, v in positive.items()}
        zero = {k: 0.0 for k, _ in positive.items()}

        vs = owner.voltage_sequence

        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]

        qua.align(sensor_dot.readout_resonator.name, *gates)

        # with qua.strict_timing_():
        vs.ramp_to_voltages(
            positive,
            duration=hold,
            ramp_duration=ramp,
            ensure_align=False,
        )
        qua.wait(wait_cycles, sensor_dot.readout_resonator.name)

        result = sensor_macro.apply(
            quantum_dot_pair_id=owner.id,
            return_iq=return_iq,
        )

        vs.ramp_to_voltages(
            negative,
            duration=hold,
            ramp_duration=16,
            ensure_align=False,
        )
        vs.ramp_to_voltages(
            zero,
            duration=16,
            ramp_duration=ramp,
            ensure_align=False,
        )

        return result

    def update(
        self,
        *,
        ramp_duration: int | None = None,
        buffer_duration: int | None = None,
        point: str | None = None,
    ) -> None:
        if ramp_duration is not None:
            self.ramp_duration = ramp_duration
        if buffer_duration is not None:
            self.buffer_duration = buffer_duration
        if point is not None:
            self.point = point


@quam_dataclass
class BalancedSensorDotMeasureMacro(QuamMacro):
    """PSB readout via the sensor readout resonator (voltage-balanced catalog).

    Copy of :class:`SensorDotMeasureMacro` for use with
    :class:`~quam_builder.architecture.quantum_dots.operations.macro_catalog.VoltageBalancedMacroCatalog`
    (priority 200), so readout can diverge from architecture defaults without
    editing the default catalog. Behavior matches the original until
    specialized.

    When called with a ``quantum_dot_pair_id``, applies the stored projector and
    threshold. With ``gate_channel_names`` and ``voltage_sequence``, aligns LF
    gates to the resonator and tracks readout time on the sequencer.
    """

    pulse_name: str = "readout"

    def _resolve_pulse_name_for_pair(self, pair_name: str | None = None) -> str | None:
        owner = _owner_component(self)
        resonator = owner.readout_resonator
        if resonator is None:
            return None
        ops = getattr(resonator, "operations", None)
        if pair_name is not None:
            pair_pulse_name = f"{self.pulse_name}_{pair_name}"
            if ops is not None and pair_pulse_name in ops:
                return pair_pulse_name
        return self.pulse_name

    def readout_pulse_length_ns_for_pair(self, pair_name: str | None = None) -> int | None:
        owner = _owner_component(self)
        resonator = owner.readout_resonator
        if resonator is None:
            return None
        pulse_name = self._resolve_pulse_name_for_pair(pair_name)
        if pulse_name is None:
            return None
        pulse = resonator.operations.get(pulse_name)
        if pulse is None:
            return None
        return _pulse_length_samples_to_ns(getattr(pulse, "length", None))

    @property
    def readout_pulse_length_ns(self) -> int | None:
        return self.readout_pulse_length_ns_for_pair(None)

    def inferred_duration_for_pair(self, qd_pair_name: str | None = None) -> float | None:
        length = self.readout_pulse_length_ns_for_pair(qd_pair_name)
        return length * 1e-9 if length is not None else None

    @property
    def inferred_duration(self) -> float | None:
        return self.inferred_duration_for_pair(None)

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        *args,
        quantum_dot_pair_id: str | None = None,
        return_iq: bool = False,
        **kwargs,
    ):
        from qm.qua import align as qua_align  # noqa: I001
        from qm.qua import declare, fixed

        owner = _owner_component(self)
        resonator = owner.readout_resonator
        readout_pulse_name = self._resolve_pulse_name_for_pair(quantum_dot_pair_id)
        if readout_pulse_name is None:
            raise ValueError("Sensor dot has no readout resonator configured.")

        i_qua = declare(fixed)
        q_qua = declare(fixed)
        resonator.measure(readout_pulse_name, qua_vars=(i_qua, q_qua))

        if quantum_dot_pair_id is None:
            return (i_qua, q_qua)

        threshold, _projector = owner._readout_params(quantum_dot_pair_id)
        state = i_qua > threshold
        if return_iq:
            return (i_qua, q_qua, state)
        return state


@quam_dataclass
class BalancedInitializeMacroWithConditionalDrive(BalancedInitializeMacro): 

    point: str = VoltagePointName.MEASURE.value
    ramp_duration: int = DEFAULTS.state_macro.ramp_duration
    buffer_duration: int = DEFAULTS.state_macro.buffer_duration
    hold_duration: int = DEFAULTS.state_macro.hold_duration

    def apply(
        self, 
        ramp_duration: int = None, 
        buffer_duration: int = None,
        hold_duration: int = None, 
        point: str | dict = None, 
        pulse_name: str = "gaussian_x180",
        return_iq: bool = False,
        xy_channel: Any = None,
        amplitude_scale: float = 1.0,
        frequency_detuning_Hz: int = 0,
    ): 
        owner = _owner_component(self)

        xy_exists = xy_channel is not None

        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        buf = self.buffer_duration if buffer_duration is None else buffer_duration
        hold_dur = self.hold_duration if hold_duration is None else hold_duration
        target_point = self.point if point is None else point

        if not owner.sensor_dots: 
            raise ValueError(f"QuantumDotPair '{owner.name}' has no sensor dots for readout")
        
        sensor_dot = owner.sensor_dots[0]
        sensor_macro = sensor_dot.macros[TwoQubitMacroName.MEASURE]
        if hasattr(sensor_macro, "readout_pulse_length_ns_for_pair"):
            readout_len = sensor_macro.readout_pulse_length_ns_for_pair(owner.id)
        else:
            readout_len = sensor_macro.readout_pulse_length_ns
        if readout_len is None:
            raise ValueError(
                "Sensor readout pulse length unknown; balanced measurement "
                "requires a fixed readout duration."
            )

        hold = buf + readout_len
        # `ramp` / `buf` may be QUA variables (e.g. when scanned via input streams),
        # so avoid Python int() casting. Right-shift by 2 == integer division by 4
        # (clock cycles), and works for both Python ints and QUA int expressions.
        if isinstance(ramp, (int, float)) and isinstance(buf, (int, float)):
            wait_cycles = int((ramp + buf) // 4)
        else:
            wait_cycles = (ramp + buf) >> 2
        positive = _point_voltages(owner, target_point)
        negative = {k: -v for k, v in positive.items()}
        zero = {k: 0.0 for k, _ in positive.items()}

        vs = owner.voltage_sequence

        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]
        elements_to_align = [sensor_dot.readout_resonator.name, *gates]
        if xy_exists: 
            elements_to_align.extend([xy_channel.id])
        qua.align(*elements_to_align)

        if xy_exists: 
            op_frequency = xy_channel.intermediate_frequency
            new_freq = op_frequency + frequency_detuning_Hz

            # Update the frequency outside of the strict timing
            xy_channel.update_frequency(new_freq)
            op_length = xy_channel.operations[pulse_name].length
        else: 
            op_length = 0

        with qua.strict_timing_():
            vs.ramp_to_voltages(
                negative,
                duration=hold + op_length + hold_dur,
                ramp_duration=ramp,
                ensure_align=False,
            )
            qua.wait(wait_cycles + readout_len//4 + hold_dur//4, sensor_dot.readout_resonator.name)

            if xy_exists: 
                qua.wait(wait_cycles + readout_len//4, xy_channel.id)
                qua.wait(op_length//4 , xy_channel.id)
                qua.wait(hold_dur//4, xy_channel.id)
                qua.wait(op_length//4, sensor_dot.readout_resonator.name)
            
            vs.ramp_to_voltages(
                positive,
                duration=hold + op_length + hold_dur,
                ramp_duration=2 * ramp,
                ensure_align=False,
            )

            qua.wait(wait_cycles + ramp//4, sensor_dot.readout_resonator.name)
            
            result = sensor_macro.apply(
                quantum_dot_pair_id=owner.id,
                return_iq=return_iq,
            )
            if xy_exists: 
                qua.wait(wait_cycles + ramp//4 + readout_len//4 , xy_channel.id)
                with qua.if_(result < 1):
                    xy_channel.play(pulse_name, amplitude_scale = amplitude_scale)
                with qua.else_():
                    qua.wait(op_length//4 , xy_channel.id)
                qua.wait(hold_dur//4, xy_channel.id)
            
            qua.wait(hold_dur//4, sensor_dot.readout_resonator.name)
            
            vs.ramp_to_voltages(
                zero,
                duration=ramp,
                ramp_duration=ramp,
                ensure_align=False,
            )

        return result
