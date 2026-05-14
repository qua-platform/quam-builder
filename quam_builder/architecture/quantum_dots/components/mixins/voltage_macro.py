"""Combined voltage-point and macro-dispatch mixin."""

# pylint: disable=too-many-ancestors

from quam.core import quam_dataclass

from .voltage_point import VoltagePointMixin
from .macro_dispatch import MacroDispatchMixin

__all__ = ["VoltageMacroMixin"]


@quam_dataclass
class VoltageMacroMixin(VoltagePointMixin, MacroDispatchMixin):
    """Full mixin combining voltage-point helpers with macro dispatch.

    This mixin consolidates all voltage control methods to reduce code duplication
    across BarrierGate, QuantumDot, QuantumDotPair, LDQubit, and LDQubitPair classes.

    Classes using this mixin must provide:
        - voltage_sequence: Property returning the VoltageSequence instance
        - id: Attribute identifying the component (used for naming points)

    Optional attributes/methods for customization:
        - machine: Property required if qubit name mapping is enabled
          current voltage tracking (if needed)

    Features:
        - Dynamic macro access: Macros in self.macros are callable as methods via __getattr__
        - Direct voltage-point creation and navigation via VoltagePointMixin
        - Serializable: All state stored in self.macros dict, compatible with QuAM serialization

    Example usage:
        @quam_dataclass
        class MyComponent(QuamComponent, VoltageMacroMixin):
            id: str
            physical_channel: VoltageGate
            points: Dict[str, Dict[str, float]] = field(default_factory=dict)

            @property
            def voltage_sequence(self) -> VoltageSequence:
                # Implementation to return voltage sequence
                ...

        # Define reusable voltage points during calibration
        component.add_point("idle", {"gate": 0.1}, duration=100)
        component.add_point("load", {"gate": 0.3}, duration=200)

        # Use direct point navigation or default architecture macros in QUA
        with program() as prog:
            component.step_to_point("idle")
            component.ramp_to_point("load", ramp_duration=500)
            component.align()
    """
