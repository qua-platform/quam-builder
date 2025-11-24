from typing import Dict, List

from quam.core import quam_dataclass, QuamComponent
from quam_builder.architecture.quantum_dots.components import VoltageGate



@quam_dataclass
class ReservoirBase(VoltageGate):
    """
    Base class for a reservoir in a quantum dot device. 
    """

    @property
    def machine(self) -> "BaseQuamQD":
        return self.quantum_dots[0].machine

    @property
    def name(self) -> str:
        return self.id



