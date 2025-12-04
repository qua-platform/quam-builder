from typing import Dict, List

from quam.core import quam_dataclass, QuamComponent
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.architecture.quantum_dots.components import VoltagePointMacroMixin, QuantumDot


@quam_dataclass
class ReservoirBase(VoltagePointMacroMixin):
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


@quam_dataclass
class Source(ReservoirBase): 
    """
    Source contact for Quantum Dot devices
    """
    physical_channel: VoltageGate = None

    
@quam_dataclass
class Drain(ReservoirBase): 
    """
    Drain contact for Quantum Dot devices
    """
    current_readout_channel = None


