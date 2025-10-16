from typing import Union

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.components import ReadoutResonatorIQ, ReadoutResonatorMW
from quam_builder.architecture.quantum_dots.components import QuantumDot

__all__ = ["SensorDot"]


@quam_dataclass
class SensorDot(QuantumDot):
    """
    Quam component for Sensor Quantum Dot 
    """

    readout_resonator: Union[ReadoutResonatorMW, ReadoutResonatorIQ]

    