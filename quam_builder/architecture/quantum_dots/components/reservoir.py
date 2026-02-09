from typing import Dict, List

from quam.core import quam_dataclass, QuamComponent

from .mixins import VoltageMacroMixin
from .quantum_dot import QuantumDot


@quam_dataclass
class ReservoirBase(VoltageMacroMixin):
    """
    Base class for a reservoir in a quantum dot device.
    """

    id: str = None
    quantum_dots: List[QuantumDot]

    @property
    def machine(self) -> "BaseQuamQD":
        # Climb up the parent ladder in order to find the VoltageSequence in the machine
        obj = self
        while obj.parent is not None:
            obj = obj.parent
        machine = obj
        return machine

    @property
    def name(self) -> str:
        return self.id
