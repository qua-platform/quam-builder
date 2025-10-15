from quam.core import quam_dataclass, QuamRoot
from readout_resonator import ReadoutResonatorBase
from quantum_dot import QuantumDot


@quam_dataclass
class Sensor(QuantumDot):
    """
    Quam component for Sensor Quantum Dot 
    """

    readout_resonator: ReadoutResonatorBase

    