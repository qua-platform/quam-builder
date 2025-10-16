from typing import Union, List
from dataclasses import field

from quam.core import quam_dataclass
from quam.components import QubitPair

from quam_builder.architecture.quantum_dots.components import QuantumDotPair, BarrierGate, SensorDot
from quam_builder.architecture.quantum_dots.qubit import LDQubit

__all__ = ["LDQubitPair"]


@quam_dataclass
class LDQubitPair(QubitPair):
    """
    A class representing a pair of LD qubits.
    """

    id: Union[str, int]

    qubit_control: LDQubit
    qubit_target: LDQubit

    barrier_gate: BarrierGate = None

    sensor_dots: List[SensorDot] = field(default_factory=list)

    def __post_init__(self): 
        self.qd_pair = QuantumDotPair(
            quantum_dots = {
                self.qubit_control.id : self.qubit_control.quantum_dot, 
                self.qubit_target.id : self.qubit_target.quantum_dot, 
            }, 
            barrier_gate = self.barrier_gate, 
            sensor_dots = self.sensor_dots
        )




