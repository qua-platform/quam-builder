from quam.core import quam_dataclass
from gate_set import GateSet
from readout_resonator import ReadoutResonatorBase

@quam_dataclass
class QuantumDot:
    """
    Quam component for a single Quantum Dot
    """
    virtualgateset: GateSet



@quam_dataclass
class Sensor(QuantumDot):
    """
    Quam component for Sensor Quantum Dot 
    """

    readout_resonator: ReadoutResonatorBase

    




