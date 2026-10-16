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
from quam_builder.tools.qua_tools import VoltageLevelType, clock_cycles_to_ns

__all__ = [
    "InitializeStateMacro",
    "EmptyStateMacro",
    "ExchangeStateMacro",
    "SensorDotMeasureMacro",
    "MeasurePSBPairMacro",
    "STATE_POINT_MACROS",
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

    ``ramp_duration`` and ``hold_duration`` are clock cycles (1 cycle = 4 ns).
    The macro converts them to nanoseconds for the voltage sequence.
    ``hold_duration``, if set, overrides the hold time; if ``None``,
    the :class:`~quam_builder.architecture.quantum_dots.components.gate_set.VoltageTuningPoint`
    ``duration`` is used, and that point duration stays in nanoseconds.
    """

    point: PointType = VoltagePointName.INITIALIZE.value
    ramp_duration: int = DEFAULTS.state_macro.ramp_duration
    hold_duration: int | None = None

    @property
    def inferred_duration(self) -> float | None:
        """Return inferred runtime duration in seconds, if available."""
        owner = _owner_component(self)
        hold = self.hold_duration
        ramp_s = self.ramp_duration * 4e-9
        if hold is None:
            hold_ns = _resolve_default_point_duration_ns(owner, self.point)
            if hold_ns is None:
                return None
            return ramp_s + hold_ns * 1e-9
        return ramp_s + hold * 4e-9

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
        hold_ns = None if hold is None else clock_cycles_to_ns(hold)
        _ramp_to_target(
            owner, self.point, ramp_duration=clock_cycles_to_ns(ramp), duration=hold_ns
        )

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

    ``hold_duration`` is in clock cycles. If it is ``None``, the hold uses the
    ``VoltageTuningPoint`` ``duration``, which stays in nanoseconds.
    """

    point: PointType = VoltagePointName.EMPTY.value
    hold_duration: int | None = None

    @property
    def inferred_duration(self) -> float | None:
        """Return inferred runtime duration in seconds, if available."""
        owner = _owner_component(self)
        hold = self.hold_duration
        if hold is None:
            hold_ns = _resolve_default_point_duration_ns(owner, self.point)
            return hold_ns * 1e-9 if hold_ns is not None else None
        return hold * 4e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, hold_duration: int | None = None, **kwargs):
        """Step to the empty target with optional hold-duration override."""
        owner = _owner_component(self)
        hold = self.hold_duration if hold_duration is None else hold_duration
        hold_ns = None if hold is None else clock_cycles_to_ns(hold)
        _step_to_target(owner, self.point, duration=hold_ns)

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
    1. Ramp to the exchange target over ``ramp_duration`` clock cycles, then
       hold at that voltage for ``wait_duration`` clock cycles (post-ramp
       plateau on ``ramp_to_voltages``).
    2. Ramp back to the initialize target over ``ramp_duration`` clock cycles
       (no extra post-ramp hold; ``duration=0`` avoids ``None`` in
       integrated-voltage tracking when QUA types are present).

    Both fields are clock cycles. The voltage sequence receives nanoseconds.
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
        exchange_return_point = self.return_point if return_point is None else return_point

        ramp_ns = clock_cycles_to_ns(ramp)
        # Ramp to exchange; hold at plateau for wait_duration clock cycles.
        _ramp_to_target(
            owner, exchange_point, ramp_duration=ramp_ns, duration=clock_cycles_to_ns(wait)
        )
        # Ramp back to initialize / return point. duration=0 is nanoseconds.
        _ramp_to_target(owner, exchange_return_point, ramp_duration=ramp_ns, duration=0)


@quam_dataclass
class SensorDotMeasureMacro(QuamMacro):
    """PSB readout via the SensorDot readout resonator with state assignment.

    When called with a ``quantum_dot_pair_id``, compares I against the stored
    threshold for that pair, returning a QUA boolean suitable for
    ``Cast.to_int()``.

    Without a pair ID, falls back to a raw resonator measurement.

    The macro does no gate alignment or voltage tracking; the calling
    measure macro (e.g. ``MeasurePSBPairMacro``) owns the timing.
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
            quantum_dot_pair_id: If provided, compare I against the threshold
                stored on this sensor dot for the given pair, returning a QUA
                boolean (I > threshold).
            voltage_sequence: Unused; kept for call compatibility.
            gate_channel_names: Unused; kept for call compatibility.
            return_iq: If True (with a pair ID), return ``(i_qua, q_qua, state)``.
            *args, **kwargs: Ignored.

        Returns:
            QUA boolean expression when ``quantum_dot_pair_id`` is set,
            otherwise ``(i_qua, q_qua)`` tuple (raw measurement).
        """

        owner = _owner_component(self)
        resonator = owner.readout_resonator
        readout_pulse_name = self._resolve_pulse_name_for_pair(quantum_dot_pair_id)
        if readout_pulse_name is None:
            raise ValueError("Sensor dot has no readout resonator configured.")

        i_qua = qua.declare(qua.fixed)
        q_qua = qua.declare(qua.fixed)
        resonator.measure(readout_pulse_name, qua_vars=(i_qua, q_qua))

        if quantum_dot_pair_id is None:
            return (i_qua, q_qua)

        threshold, _ = owner._readout_params(quantum_dot_pair_id)

        state = i_qua > threshold  # Assuming that the readout projects onto the I axis
        if return_iq:
            return (i_qua, q_qua, state)
        return state


@quam_dataclass
class MeasurePSBPairMacro(QuamMacro):
    """PSB measure macro for QuantumDotPair.

    The timing sequence is:

    1. **Align** -- synchronize the voltage gate channels with the readout
       resonator.
    2. **Ramp + buffer** -- ramp to the measure voltage point over
       ``ramp_duration`` clock cycles, then hold for ``buffer_duration``
       clock cycles (settling time before readout). The resonator waits
       for the same ``ramp + buffer`` cycles.
    3. **Readout** -- the sensor macro plays the readout pulse while the
       gates keep holding the measure point, so the readout time is
       included in integrated-voltage tracking.

    Returns a QUA boolean for state discrimination.
    """

    point: PointType = VoltagePointName.MEASURE.value
    buffer_duration: int | None = DEFAULTS.state_macro.buffer_duration
    ramp_duration: int | None = DEFAULTS.state_macro.ramp_duration

    @property
    def inferred_duration(self) -> float | None:
        """Total duration = ramp + buffer + sensor readout (seconds)."""
        owner = _owner_component(self)
        buffer_s = (self.buffer_duration or 0) * 4e-9
        ramp_s = (self.ramp_duration or 0) * 4e-9
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
        return buffer_s + sensor_dur + ramp_s

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, buffer_duration: int | None = None, ramp_duration: int | None = None, **kwargs):
        """Step to measure target, then perform PSB readout via sensor dot."""
        owner = _owner_component(self)

        buf = self.buffer_duration if buffer_duration is None else buffer_duration
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        ramp_ns = clock_cycles_to_ns(ramp)
        buffer_ns = clock_cycles_to_ns(buf)

        if not owner.sensor_dots:
            raise ValueError(f"QuantumDotPair '{owner.id}' has no sensor dots for readout.")
        sensor_dot = owner.sensor_dots[0]
        rr = sensor_dot.readout_resonator
        gate_names = []
        vs = getattr(owner, "voltage_sequence", None)
        if vs is not None:
            gate_set = getattr(vs, "gate_set", None)
            if gate_set is not None:
                gate_names = [ch.name for ch in gate_set.channels.values()]

        # Align the readout resonator to the gates of the VoltageSequence
        qua.align(rr.name, *gate_names)
        sensor_macro = sensor_dot.macros[TwoQubitMacroName.MEASURE]
        readout_duration_ns = sensor_macro.readout_pulse_length_ns_for_pair(owner.id)
        if readout_duration_ns is None: 
            raise ValueError("Readout duration not found. Please double check Quam state.")

        # Step to the point. The readout resonator should wait for the ramp + buffer, and then start reading
        _ramp_to_target(owner, self.point, ramp_duration = ramp_ns, duration=buffer_ns + readout_duration_ns)
        qua.wait((buf + ramp), rr.name) # QUA's wait command in clock cycles

        return sensor_macro.apply(
            quantum_dot_pair_id=owner.id,
            voltage_sequence=vs,
            gate_channel_names=None,
            **kwargs,
        )

    def update(
        self,
        *,
        buffer_duration: int | None = None,
        ramp_duration: int | None = None,
        point: PointType | None = None,
    ) -> None:
        """Persistently update calibrated measure parameters."""
        if buffer_duration is not None:
            self.buffer_duration = buffer_duration
        if ramp_duration is not None: 
            self.ramp_duration = ramp_duration
        if point is not None:
            self.point = point

STATE_POINT_MACROS = {
    VoltagePointName.INITIALIZE.value: InitializeStateMacro,
    VoltagePointName.EMPTY.value: EmptyStateMacro,
}
# Default state-macro factories for point-capable components.
