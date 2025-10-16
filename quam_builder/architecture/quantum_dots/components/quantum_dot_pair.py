from typing import Dict, List, Union
from dataclasses import field

from quam.core import quam_dataclass


from quam_builder.architecture.quantum_dots.components.quantum_dot import QuantumDot
from quam_builder.architecture.quantum_dots.components.sensor_dot import SensorDot
from quam_builder.architecture.quantum_dots.components.barrier_gate import BarrierGate

__all__ = ["QuantumDotPair"]


@quam_dataclass
class QuantumDotPair:

    quantum_dots: Dict[str, QuantumDot]
    barrier_gate: BarrierGate
    dot_capacitance: float = 0
    barrier_capacitances: Dict[str, float] = field(default_factory = dict)
    sensor_dots: List[SensorDot]

    def __post_init__(self): 
        for qd in self.quantum_dots: 
            self.barrier_capacitances[qd] = 0

        







