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
        couplings (Dict): A dictionary holding the coupling value of each QuantumDot instance to the BarrierGate.
            Each couplings entry must be of the form {element_id: {dot1.id: value, dot2.id: value}}. The values default to zero at instantiation

            >>> Example implementation:
            >>> 
            >>> qubit1 = LDQubit(quantum_dot = dot1)
            >>> qubit2 = LDQubit(quantum_dot = dot2)
            >>> sensor_dot = SensorDot(id = "sensor", physical_channel = VoltageGate(...), resonator = ...)
            >>> barrier_gate = BarrierGate(id = "barrier", opx_output = ...)
            >>>
            >>> qubit_pair_1 = LDQubitPair(
            ...     qubit_control = qubit1, 
            ...     qubit_target = qubit2,
            ...     dot_coupling = 0.2,
            ...     sensor_dots = [sensor_dot], # Can include more than one sensor
            ...     barrier_gate = barrier_gate 
            ... )
            >>> qubit_pair_1.couplings[barrier_gate.id] = {
            ...     qubit1.id : 0.01, 
            ...     qubit2.id : 0.02
            ... }
            >>> qubit_pair_1.couplings[sensor_dot.id] = {
            ...     qubit1.id: 0.1, 
            ...     qubit2.id: 0.15
            ... }

    """

    id: Union[str, int]

    qubit_control: LDQubit
    qubit_target: LDQubit

    dot_coupling: float = 0.0
    barrier_gate: BarrierGate = None

    sensor_dots: List[SensorDot] = field(default_factory=list)
    couplings: Dict[str, Dict[str, float]] = field(default_factory = dict)

    def __post_init__(self): 
        if self.id is None:
            self.id = f"{self.qubit_control.id}_{self.qubit_target.id}"

        self.qd_pair = QuantumDotPair(
            quantum_dots = [
                self.qubit_control.quantum_dot, 
                self.qubit_target.quantum_dot, 
            ],
            dot_coupling = self.dot_coupling,
            barrier_gate = self.barrier_gate, 
            sensor_dots = self.sensor_dots,
            couplings = self.couplings.copy()
        )
        self.couplings = self.qd_pair.couplings




