from typing import Union, List, Dict
from dataclasses import field

from quam.core import quam_dataclass
from quam.components import QubitPair

from quam_builder.architecture.quantum_dots.components import QuantumDotPair, BarrierGate, SensorDot
from quam_builder.architecture.quantum_dots.qubit import LDQubit

__all__ = ["LDQubitPair"]


@quam_dataclass
class LDQubitPair(QubitPair):
    """
    Class representing a Loss-DiVincenzo Qubit Pair. 
    Internally, a QuantumDotPair will be instantiated.

    Attributes: 
        qubit_control (LDQubit): The first Loss-DiVincenzo Qubit instance
        qubit_target (LDQubit): The second Loss-DiVincenzo Qubit instance
        barrier_gate (BarrierGate): The BarrierGate instance between the two QuantumDots.  
        sensor_dots (List[SensorDot]): A list of SensorDot instances coupled to this particular QuantumDot pair. 
        dot_coupling (float): A value representing the coupling strength of the QuantumDot pair.


    """

    id: Union[str, int]

    qubit_control: LDQubit
    qubit_target: LDQubit

    def __post_init__(self): 
        if self.id is None:
            self.id = f"{self.qubit_control.name}_{self.qubit_target.name}"
    
    @property
    def detuning_axis_name(self): 
        return self.quantum_dot_pair.detuning_axis_name
    
    @property
    def voltage_sequence(self): 
        return self.quantum_dot_pair.voltage_sequence
    
    def add_quantum_dot_pair(self, quantum_dot_pair: QuantumDotPair): 
        self.quantum_dot_pair = quantum_dot_pair






