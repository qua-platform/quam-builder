"""State macros shared across quantum-dot component types."""

from __future__ import annotations

from numbers import Integral, Real
from typing import Any, Optional

from qm import qua
from quam.core import quam_dataclass
from quam.core.macro import QuamMacro
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from quam_builder.architecture.quantum_dots.operations.names import (
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.tools.qua_tools import CLOCK_CYCLE_NS, VoltageLevelType

__all__ = [
    "InitializeStateMacro",
    "EmptyStateMacro",
    "ExchangeStateMacro",
    "SensorDotMeasureMacro",
    "MeasurePSBPairMacro",
    "QPUInitializeMacro",
    "QPUMeasureMacro",
    "QPUEmptyMacro",
    "STATE_POINT_MACROS",
    "QPU_STATE_MACROS",
]

PointType = str | dict[str, VoltageLevelType]

# ``update()`` sentinel: keyword was omitted (vs. explicitly passed ``None``).
_OMIT_HOLD_UPDATE = object()


def _pulse_length_samples_to_ns(length: Any) -> int | None:
    """Return pulse length in nanoseconds (1 sample = 1 ns on OPX)."""
    if isinstance(length, Integral):
        return int(length)
    if isinstance(length, Real) and float(length).is_integer():
        return int(length)
    return None


def _owner_component(macro: QuamMacro) -> Any:
    """Resolve the component that owns a macro instance.

    The parent may be either the component itself or an intermediate mapping
    object (for example, a QuAM dict wrapper around ``component.macros``).
    """
    direct_parent = getattr(macro, "parent", None)
    if direct_parent is None:
        raise ValueError("Macro is not attached to a component.")

    # Macro parent can be either the owning component or an intermediate dict-like object.
    if hasattr(direct_parent, "step_to_point") or hasattr(direct_parent, "macros"):
        return direct_parent

    owner = getattr(direct_parent, "parent", None)
    if owner is None:
        raise ValueError("Could not resolve macro owner component.")
    return owner


def _resolve_default_point_duration_ns(owner: Any, point: PointType) -> int | None:
    """Best-effort lookup of a point's default hold duration in nanoseconds."""
    if not isinstance(point, str):
        return None
    try:
        full_name = owner._create_point_name(point)
        point = owner.voltage_sequence.gate_set.macros[full_name]
        duration = getattr(point, "duration", None)
        if isinstance(duration, int):
            return duration
    except Exception:  # pragma: no cover - defensive
        return None
    return None


def _step_to_target(owner: Any, point: PointType, duration: int | None = None) -> None:
    """Step to either a named point or an explicit voltage dictionary."""
    if isinstance(point, str):
        owner.step_to_point(point, duration=duration)
        return
    owner.step_to_voltages(point, duration=duration)


def _ramp_to_target(
    owner: Any,
    point: PointType,
    ramp_duration: int,
    duration: int | None = None,
) -> None:
    """Ramp to either a named point or an explicit voltage dictionary."""
    if isinstance(point, str):
        owner.ramp_to_point(point, ramp_duration=ramp_duration, duration=duration)
        return
    owner.ramp_to_voltages(point, duration=duration, ramp_duration=ramp_duration)


@quam_dataclass
class InitializeStateMacro(QuamMacro):
    """Move component to initialize voltages using a ramp transition.

    ``hold_duration`` on this macro, if set, overrides the hold time; if ``None``,
    the :class:`~quam_builder.architecture.quantum_dots.components.gate_set.VoltageTuningPoint`
    ``duration`` is used (via ``ramp_to_*`` with ``duration=None``).
    """

    point: PointType = VoltagePointName.INITIALIZE.value
    ramp_duration: int = DEFAULTS.state_macro.ramp_duration
    hold_duration: int | None = None

    @property
    def inferred_duration(self) -> float | None:
        """Return inferred runtime duration in seconds, if available."""
        owner = _owner_component(self)
        hold = self.hold_duration
        if hold is None:
            hold = _resolve_default_point_duration_ns(owner, self.point)
        if hold is None:
            return None
        return (self.ramp_duration + hold) * 1e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        ramp_duration: int | None = None,
        hold_duration: int | None = None,
        **kwargs,
    ):
        """Ramp to the initialize target with optional runtime overrides."""
        owner = _owner_component(self)
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        hold = self.hold_duration if hold_duration is None else hold_duration
        _ramp_to_target(owner, self.point, ramp_duration=ramp, duration=hold)

    def update(
        self,
        *,
        ramp_duration: int | None = None,
        hold_duration: int | None | object = _OMIT_HOLD_UPDATE,
        point: PointType | None = None,
    ) -> None:
        """Persistently update calibrated initialization parameters."""
        if ramp_duration is not None:
            self.ramp_duration = ramp_duration
        if hold_duration is not _OMIT_HOLD_UPDATE:
            self.hold_duration = hold_duration  # type: ignore[assignment]
        if point is not None:
            self.point = point


@quam_dataclass
class EmptyStateMacro(QuamMacro):
    """Move component to empty voltages.

    If ``hold_duration`` is ``None``, the hold uses the ``VoltageTuningPoint`` ``duration``.
    """

    point: PointType = VoltagePointName.EMPTY.value
    hold_duration: int | None = None

    @property
    def inferred_duration(self) -> float | None:
        """Return inferred runtime duration in seconds, if available."""
        owner = _owner_component(self)
        hold = self.hold_duration
        if hold is None:
            hold = _resolve_default_point_duration_ns(owner, self.point)
        return hold * 1e-9 if hold is not None else None

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, hold_duration: int | None = None, **kwargs):
        """Step to the empty target with optional hold-duration override."""
        owner = _owner_component(self)
        hold = self.hold_duration if hold_duration is None else hold_duration
        _step_to_target(owner, self.point, duration=hold)

    def update(
        self,
        *,
        hold_duration: int | None | object = _OMIT_HOLD_UPDATE,
        point: PointType | None = None,
    ) -> None:
        """Persistently update calibrated empty parameters."""
        if hold_duration is not _OMIT_HOLD_UPDATE:
            self.hold_duration = hold_duration  # type: ignore[assignment]
        if point is not None:
            self.point = point


@quam_dataclass
class ExchangeStateMacro(QuamMacro):
    """Ramp to exchange target, hold, then ramp back to initialize.

    The sequence is:
    1. Ramp to the exchange target over ``ramp_duration`` ns, then hold at that
       voltage for ``wait_duration`` ns (post-ramp plateau on
       ``ramp_to_voltages`` — equivalent to the former separate sticky
       ``step_to_voltages`` wait).
    2. Ramp back to the initialize target over ``ramp_duration`` ns (no extra
       post-ramp hold; ``duration=0`` avoids ``None`` in integrated-voltage
       tracking when QUA types are present).
    """

    point: PointType = VoltagePointName.EXCHANGE.value
    return_point: PointType = VoltagePointName.INITIALIZE.value
    ramp_duration: int = DEFAULTS.exchange.ramp_duration
    wait_duration: int = DEFAULTS.exchange.wait_duration

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        ramp_duration: int | None = None,
        wait_duration: int | None = None,
        point: PointType | None = None,
        return_point: PointType | None = None,
        **kwargs,
    ):
        """Execute the exchange pulse sequence with optional runtime overrides."""
        owner = _owner_component(self)
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        wait = self.wait_duration if wait_duration is None else wait_duration
        exchange_point = self.point if point is None else point
        exchange_return_point = (
            self.return_point if return_point is None else return_point
        )

        # Ramp to exchange; hold at plateau for wait_duration (ns after ramp completes)
        _ramp_to_target(owner, exchange_point, ramp_duration=ramp, duration=wait)
        # Ramp back to initialize / return point
        _ramp_to_target(owner, exchange_return_point, ramp_duration=ramp, duration=0)


@quam_dataclass
class SensorDotMeasureMacro(QuamMacro):
    """PSB readout via the SensorDot readout resonator with state assignment.

    When called with a ``quantum_dot_pair_id``, applies the stored
    projector and threshold for that pair to perform state discrimination,
    returning a QUA boolean suitable for ``Cast.to_int()``.

    Without a pair ID, falls back to a raw resonator measurement.

    When ``gate_channel_names`` and ``voltage_sequence`` are provided
    (typically by ``MeasurePSBPairMacro``), the macro aligns the voltage
    gates with the resonator before measuring and tracks the elapsed
    readout time on the voltage sequencer so integrated-voltage
    bookkeeping stays correct.
    """

    pulse_name: str = "readout"


    def _resolve_pulse_name_for_pair(self, pair_name: Optional[str] = None) -> str | None:
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

    def readout_pulse_length_ns_for_pair(self, pair_name: Optional[str] = None) -> int | None:
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
        """Length of the readout pulse in nanoseconds, or ``None``."""
        return self.readout_pulse_length_ns_for_pair(None)

    def inferred_duration_for_pair(self, qd_pair_name: Optional[str] = None) -> float | None:
        length = self.readout_pulse_length_ns_for_pair(qd_pair_name)
        return length * 1e-9 if length is not None else None

    @property
    def inferred_duration(self) -> float | None:
        """Duration dictated by the readout pulse length (seconds)."""
        return self.inferred_duration_for_pair(None)

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        *args,
        quantum_dot_pair_id: str | None = None,
        voltage_sequence=None,
        gate_channel_names: list[str] | None = None,
        return_iq: bool = False,
        **kwargs,
    ):
        """Measure the readout resonator and optionally perform state assignment.

        Args:
            quantum_dot_pair_id: If provided, apply the projector and threshold
                stored on this sensor dot for the given pair, returning a QUA
                boolean (projected_value > threshold).
            voltage_sequence: Voltage sequencer for integrated-voltage tracking.
            gate_channel_names: QUA element names of voltage gate channels to
                align with the readout resonator before measuring.
            *args, **kwargs: Forwarded to ``readout_resonator.measure()`` when
                no pair ID is given.

        Returns:
            QUA boolean expression when ``quantum_dot_pair_id`` is set,
            otherwise ``(i_qua, q_qua)`` tuple (raw measurement).
        """
        from qm.qua import declare, fixed

        owner = _owner_component(self)
        resonator = owner.readout_resonator
        readout_pulse_name = self._resolve_pulse_name_for_pair(quantum_dot_pair_id)
        if readout_pulse_name is None:
            raise ValueError("Sensor dot has no readout resonator configured.")

        # if gate_channel_names:
        #     qua.align(*gate_channel_names, resonator.name)

        # if voltage_sequence is not None:
        #     pulse_length_ns = self.readout_pulse_length_ns_for_pair(quantum_dot_pair_id)
        #     if pulse_length_ns is not None:
        #         voltage_sequence.step_to_voltages({}, pulse_length_ns, ensure_align=False)

        i_qua = declare(fixed)
        q_qua = declare(fixed)
        resonator.measure(readout_pulse_name, qua_vars=(i_qua, q_qua))

        if quantum_dot_pair_id is None:
            return (i_qua, q_qua)

        threshold, projector = owner._readout_params(quantum_dot_pair_id)
        # wI = float(projector.get("wI", 1.0))
        # wQ = float(projector.get("wQ", 0.0))
        # offset = float(projector.get("offset", 0.0))

        # projected = declare(fixed)
        # assign(projected, i_qua * wI + q_qua * wQ + offset)

        state = i_qua > threshold # Assuming that the readout projects onto the I axis
        if return_iq:
            return (i_qua, q_qua, state)
        return state


@quam_dataclass
class MeasurePSBPairMacro(QuamMacro):
    """PSB measure macro for QuantumDotPair.

    The timing sequence is:

    1. **Buffer** -- step to the measure voltage point for
       ``buffer_duration`` ns (settling time before readout).
    2. **Align** -- synchronize voltage gate channels with the readout
       resonator (handled inside the sensor macro).
    3. **Readout + track** -- the sensor macro plays the readout pulse
       and calls ``track_sticky_duration`` on the voltage sequencer so
       integrated-voltage bookkeeping stays correct.

    Returns a QUA boolean for state discrimination.
    """

    point: PointType = VoltagePointName.MEASURE.value
    buffer_duration: int | None = DEFAULTS.state_macro.buffer_duration

    @property
    def inferred_duration(self) -> float | None:
        """Total duration = buffer + sensor readout (seconds)."""
        owner = _owner_component(self)
        buffer_ns = self.buffer_duration or 0
        if not getattr(owner, "sensor_dots", None):
            return None
        sensor_dot = owner.sensor_dots[0]
        sensor_macro = sensor_dot.macros.get(TwoQubitMacroName.MEASURE)
        if sensor_macro is None:
            return None
        if hasattr(sensor_macro, "inferred_duration_for_pair"):
            sensor_dur = sensor_macro.inferred_duration_for_pair(owner.id)
        else:
            sensor_dur = sensor_macro.inferred_duration
        if sensor_dur is None:
            return None
        return (buffer_ns * 1e-9) + sensor_dur

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, buffer_duration: int | None = None, **kwargs):
        """Step to measure target, then perform PSB readout via sensor dot."""
        owner = _owner_component(self)
        buf = self.buffer_duration if buffer_duration is None else buffer_duration
        _step_to_target(owner, self.point, duration=buf)

        if not owner.sensor_dots:
            raise ValueError(
                f"QuantumDotPair '{owner.id}' has no sensor dots for readout."
            )
        sensor_dot = owner.sensor_dots[0]

        gate_names = []
        vs = getattr(owner, "voltage_sequence", None)
        if vs is not None:
            gate_set = getattr(vs, "gate_set", None)
            if gate_set is not None:
                gate_names = [ch.name for ch in gate_set.channels.values()]

        qua.align(sensor_dot.readout_resonator.name, *gate_names)

        return sensor_dot.macros[TwoQubitMacroName.MEASURE].apply(
            quantum_dot_pair_id=owner.id,
            voltage_sequence=vs,
            gate_channel_names=None,
            **kwargs,
        )

    def update(
        self,
        *,
        buffer_duration: int | None = None,
        point: PointType | None = None,
    ) -> None:
        """Persistently update calibrated measure parameters."""
        if buffer_duration is not None:
            self.buffer_duration = buffer_duration
        if point is not None:
            self.point = point


def _iter_qpu_targets(machine: Any):
    """Yield components targeted by QPU-level state macros.

    Priority order:
        1. Active qubits/pairs if explicitly set.
        2. All registered qubits/pairs.
        3. Fallback to quantum dots/pairs for stage-1 machines.
    """
    if getattr(machine, "active_qubit_names", None):
        for name in machine.active_qubit_names:
            yield machine.qubits[name]
    elif getattr(machine, "qubits", None):
        yield from machine.qubits.values()
    elif getattr(machine, "quantum_dots", None):
        yield from machine.quantum_dots.values()

    if getattr(machine, "active_qubit_pair_names", None):
        for name in machine.active_qubit_pair_names:
            yield machine.qubit_pairs[name]
    elif getattr(machine, "qubit_pairs", None):
        yield from machine.qubit_pairs.values()
    elif getattr(machine, "quantum_dot_pairs", None):
        yield from machine.quantum_dot_pairs.values()


@quam_dataclass
class _QPUStateDispatchMacro(QuamMacro):
    """Dispatch a state macro to active machine components."""

    macro_name: str

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        """Dispatch configured state macro to each selected machine target."""
        owner = _owner_component(self)
        machine = getattr(owner, "machine", None)
        if machine is None:
            raise ValueError("QPU macro owner has no machine.")

        results = {}
        for component in _iter_qpu_targets(machine):
            results[component.id] = component.macros[self.macro_name].apply(**kwargs)
        return results


@quam_dataclass
class QPUInitializeMacro(_QPUStateDispatchMacro):
    """QPU-level dispatch macro for ``initialize`` state transition."""

    macro_name: str = VoltagePointName.INITIALIZE.value


@quam_dataclass
class QPUMeasureMacro(_QPUStateDispatchMacro):
    """QPU-level dispatch macro for ``measure`` state transition."""

    macro_name: str = VoltagePointName.MEASURE.value


@quam_dataclass
class QPUEmptyMacro(_QPUStateDispatchMacro):
    """QPU-level dispatch macro for ``empty`` state transition."""

    macro_name: str = VoltagePointName.EMPTY.value


STATE_POINT_MACROS = {
    VoltagePointName.INITIALIZE.value: InitializeStateMacro,
    VoltagePointName.EMPTY.value: EmptyStateMacro,
}
# Default state-macro factories for point-capable components.

QPU_STATE_MACROS = {
    VoltagePointName.INITIALIZE.value: QPUInitializeMacro,
    VoltagePointName.MEASURE.value: QPUMeasureMacro,
    VoltagePointName.EMPTY.value: QPUEmptyMacro,
}
# Default state-macro factories for the machine-level QPU component.
