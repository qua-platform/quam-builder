"""State macros shared across quantum-dot component types."""

from __future__ import annotations

from typing import Any, ClassVar, Optional

from quam.core import quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.operations.names import VoltagePointName

__all__ = [
    "InitializeStateMacro",
    "MeasureStateMacro",
    "EmptyStateMacro",
    "SensorDotMeasureMacro",
    "MeasurePSBPairMacro",
    "QPUInitializeMacro",
    "QPUMeasureMacro",
    "QPUEmptyMacro",
    "STATE_POINT_MACROS",
    "QPU_STATE_MACROS",
]


def _owner_component(macro: QuamMacro) -> Any:
    """Resolve the component that owns a macro instance.

    The parent may be either the component itself or an intermediate mapping
    object (for example, a QuAM dict wrapper around ``component.macros``).
    """
    direct_parent = getattr(macro, "parent", None)
    if direct_parent is None:
        raise ValueError("Macro is not attached to a component.")

    # Macro parent can be either the owning component or an intermediate dict-like object.
    if hasattr(direct_parent, "step_to_point") or hasattr(direct_parent, "call_macro"):
        return direct_parent

    owner = getattr(direct_parent, "parent", None)
    if owner is None:
        raise ValueError("Could not resolve macro owner component.")
    return owner


def _resolve_default_point_duration_ns(owner: Any, point_name: str) -> Optional[int]:
    """Best-effort lookup of a point's default hold duration in nanoseconds."""
    try:
        full_name = owner._create_point_name(point_name)
        point = owner.voltage_sequence.gate_set.macros[full_name]
        duration = getattr(point, "duration", None)
        if isinstance(duration, int):
            return duration
    except Exception:  # pragma: no cover - defensive
        return None
    return None


@quam_dataclass
class InitializeStateMacro(QuamMacro):
    """Move component to initialize voltage point using a ramp transition.

    Notes:
        - ``updates_voltage_tracking=True`` because voltage tracking is already
          handled by the voltage-sequence helpers called by this macro.
    """

    point_name: str = VoltagePointName.INITIALIZE.value
    ramp_duration: int = 16
    hold_duration: int | None = None
    updates_voltage_tracking: ClassVar[bool] = True

    @property
    def inferred_duration(self) -> float | None:
        """Return inferred runtime duration in seconds, if available."""
        owner = _owner_component(self)
        hold = self.hold_duration
        if hold is None:
            hold = _resolve_default_point_duration_ns(owner, self.point_name)
        if hold is None:
            return None
        return (self.ramp_duration + hold) * 1e-9

    def apply(
        self,
        ramp_duration: int | None = None,
        hold_duration: int | None = None,
        **kwargs,
    ):
        """Ramp to the initialize point with optional runtime overrides."""
        owner = _owner_component(self)
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        hold = self.hold_duration if hold_duration is None else hold_duration
        owner.ramp_to_point(self.point_name, ramp_duration=ramp, duration=hold)


@quam_dataclass
class MeasureStateMacro(QuamMacro):
    """Move component to measure voltage point."""

    point_name: str = VoltagePointName.MEASURE.value
    hold_duration: int | None = None
    updates_voltage_tracking: ClassVar[bool] = True

    @property
    def inferred_duration(self) -> float | None:
        """Return inferred runtime duration in seconds, if available."""
        owner = _owner_component(self)
        hold = self.hold_duration
        if hold is None:
            hold = _resolve_default_point_duration_ns(owner, self.point_name)
        return hold * 1e-9 if hold is not None else None

    def apply(self, hold_duration: int | None = None, **kwargs):
        """Step to the measure point with optional hold-duration override."""
        owner = _owner_component(self)
        hold = self.hold_duration if hold_duration is None else hold_duration
        owner.step_to_point(self.point_name, duration=hold)


@quam_dataclass
class EmptyStateMacro(QuamMacro):
    """Move component to empty voltage point."""

    point_name: str = VoltagePointName.EMPTY.value
    hold_duration: int | None = None
    updates_voltage_tracking: ClassVar[bool] = True

    @property
    def inferred_duration(self) -> float | None:
        """Return inferred runtime duration in seconds, if available."""
        owner = _owner_component(self)
        hold = self.hold_duration
        if hold is None:
            hold = _resolve_default_point_duration_ns(owner, self.point_name)
        return hold * 1e-9 if hold is not None else None

    def apply(self, hold_duration: int | None = None, **kwargs):
        """Step to the empty point with optional hold-duration override."""
        owner = _owner_component(self)
        hold = self.hold_duration if hold_duration is None else hold_duration
        owner.step_to_point(self.point_name, duration=hold)


@quam_dataclass
class SensorDotMeasureMacro(QuamMacro):
    """PSB readout via the SensorDot readout resonator with state assignment.

    When called with a ``quantum_dot_pair_id``, applies the stored
    projector and threshold for that pair to perform state discrimination,
    returning a QUA boolean suitable for ``Cast.to_int()``.

    Without a pair ID, falls back to a raw resonator measurement.
    """

    pulse_name: str = "readout"

    def apply(self, *args, quantum_dot_pair_id: Optional[str] = None, **kwargs):
        """Measure the readout resonator and optionally perform state assignment.

        Args:
            quantum_dot_pair_id: If provided, apply the projector and threshold
                stored on this sensor dot for the given pair, returning a QUA
                boolean (projected_value > threshold).
            *args, **kwargs: Forwarded to ``readout_resonator.measure()`` when
                no pair ID is given.

        Returns:
            QUA boolean expression when ``quantum_dot_pair_id`` is set,
            otherwise ``None`` (raw measurement stored in qua_vars).
        """
        from qm.qua import declare, fixed, assign

        owner = _owner_component(self)

        if quantum_dot_pair_id is None:
            owner.readout_resonator.measure(*args, **kwargs)
            return None

        I = declare(fixed)
        Q = declare(fixed)
        owner.readout_resonator.measure(self.pulse_name, qua_vars=(I, Q))

        threshold, projector = owner._readout_params(quantum_dot_pair_id)
        wI = projector.get("wI", 1.0)
        wQ = projector.get("wQ", 0.0)
        offset = projector.get("offset", 0.0)

        x = declare(fixed)
        assign(x, I * wI + Q * wQ + offset)
        return x > threshold


@quam_dataclass
class MeasurePSBPairMacro(QuamMacro):
    """PSB measure macro for QuantumDotPair.

    Steps to the measure voltage point, then dispatches readout to the
    first coupled sensor dot with the pair ID for threshold lookup.
    Returns a QUA boolean for state discrimination.
    """

    point_name: str = VoltagePointName.MEASURE.value
    hold_duration: int | None = None
    updates_voltage_tracking: ClassVar[bool] = True

    def apply(self, hold_duration: int | None = None, **kwargs):
        """Step to measure point, then perform PSB readout via sensor dot."""
        owner = _owner_component(self)
        hold = self.hold_duration if hold_duration is None else hold_duration
        owner.step_to_point(self.point_name, duration=hold)

        if not owner.sensor_dots:
            raise ValueError(f"QuantumDotPair '{owner.id}' has no sensor dots for readout.")
        sensor_dot = owner.sensor_dots[0]
        return sensor_dot.call_macro(
            VoltagePointName.MEASURE.value,
            quantum_dot_pair_id=owner.id,
        )


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
    updates_voltage_tracking: ClassVar[bool] = True

    def apply(self, **kwargs):
        """Dispatch configured state macro to each selected machine target."""
        owner = _owner_component(self)
        machine = getattr(owner, "machine", None)
        if machine is None:
            raise ValueError("QPU macro owner has no machine.")

        results = {}
        for component in _iter_qpu_targets(machine):
            call_macro = getattr(component, "call_macro", None)
            if callable(call_macro):
                results[component.id] = call_macro(self.macro_name, **kwargs)
            else:
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
    VoltagePointName.MEASURE.value: MeasureStateMacro,
    VoltagePointName.EMPTY.value: EmptyStateMacro,
}
# Default state-macro factories for point-capable components.

QPU_STATE_MACROS = {
    VoltagePointName.INITIALIZE.value: QPUInitializeMacro,
    VoltagePointName.MEASURE.value: QPUMeasureMacro,
    VoltagePointName.EMPTY.value: QPUEmptyMacro,
}
# Default state-macro factories for the machine-level QPU component.
