from typing import Union
from dataclasses import field

from pygments.lexer import default
from quam.core import quam_dataclass
from quam.components import InOutSingleChannel

from quam_builder.architecture.quantum_dots.components import (
    ReadoutResonatorIQ,
    ReadoutResonatorMW,
)
from quam_builder.architecture.quantum_dots.components import QuantumDot

__all__ = ["SensorDot"]


@quam_dataclass
class SensorDot(QuantumDot):
    """
    Quam component for Sensor Quantum Dot
    """

    readout_resonator: Union[ReadoutResonatorMW, ReadoutResonatorIQ]
    state_thresholds: dict = field(default_factory=dict)

    def _readout_threshold(
        self, quantum_dot_pair_id
    ) -> Union[ReadoutResonatorIQ, ReadoutResonatorMW]:
        return self.state_thresholds[quantum_dot_pair_id]
