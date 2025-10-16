from typing import Dict, List, Union
from dataclasses import field

from quam.core import quam_dataclass


from quam_builder.architecture.quantum_dots.components import QuantumDot, SensorDot, BarrierGate

__all__ = ["QuantumDotPair"]


@quam_dataclass
class QuantumDotPair:

    quantum_dots: Dict[str, QuantumDot]
    barrier: BarrierGate
    dot_capacitance: float = 0
    barrier_capacitances: Dict[str, float] = field(default_factory = dict)

    def __post_init__(self): 
        for qd in self.quantum_dots: 
            self.barrier_capacitances[qd] = 0

        







