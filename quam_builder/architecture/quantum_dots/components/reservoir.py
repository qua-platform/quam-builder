"""Reservoir component definitions for quantum dot systems."""

from typing import TYPE_CHECKING, List

from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.components.voltage_gate import VoltageGate
from quam_builder.architecture.quantum_dots.components.mixin import VoltagePointMacroMixin
from quam_builder.architecture.quantum_dots.components.quantum_dot import QuantumDot

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD


@quam_dataclass
class ReservoirBase(VoltagePointMacroMixin):
    """
    Base class for a reservoir in a quantum dot device.
    """

    id: str = None
    quantum_dots: List[QuantumDot]

    @property
    def machine(self) -> "BaseQuamQD":
        """Return the owning machine by walking parent references."""
        # Climb up the parent ladder in order to find the VoltageSequence in the machine
        obj = self
        while obj.parent is not None:
            obj = obj.parent
        machine = obj
        return machine

    @property
    def name(self) -> str:
        """Return the reservoir identifier."""
        return self.id
