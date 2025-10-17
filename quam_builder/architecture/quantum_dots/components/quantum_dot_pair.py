from typing import Dict, List, Union
from dataclasses import field

from quam.core import quam_dataclass


from quam_builder.architecture.quantum_dots.components.quantum_dot import QuantumDot
from quam_builder.architecture.quantum_dots.components.sensor_dot import SensorDot
from quam_builder.architecture.quantum_dots.components.barrier_gate import BarrierGate

__all__ = ["QuantumDotPair"]


@quam_dataclass
class QuantumDotPair:

    """
    Class representing a Quantum Dot Pair. 
    Attributes: 
        quantum_dots (List[QuantumDot]): A list of the two QuantumDot instances to be paired. 
        barrier_gate (BarrierGate): The BarrierGate instance between the two QuantumDots.  
        sensor_dots (List[SensorDot]): A list of SensorDot instances coupled to this particular QuantumDot pair. 
        dot_coupling (float): A value representing the coupling strength of the QuantumDot pair.
        couplings (Dict): A dictionary holding the coupling value of each QuantumDot instance to the BarrierGate.
            Each couplings entry must be of the form {element_id: {dot1.id: value, dot2.id: value}}. The values default to zero at instantiation

            >>> Example implementation:
            >>> 
            >>> dot1 = QuantumDot(id = "dot1", physical_channel = VoltageGate(...))
            >>> dot2 = QuantumDot(id = "dot2", physical_channel = VoltageGate(...))
            >>> sensor_dot = SensorDot(id = "sensor", physical_channel = VoltageGate(...), resonator = ...)
            >>> barrier_gate = BarrierGate(id = "barrier", opx_output = ...)
            >>>
            >>> dot_pair_1 = QuantumDotPair(
            ...     quantum_dots = [dot1, dot2], 
            ...     dot_coupling = 0.2,
            ...     sensor_dots = [sensor_dot], # Can include more than one sensor
            ...     barrier_gate = barrier_gate 
            ... )
            >>> dot_pair_1.couplings[barrier_gate.id] = {
            ...     dot1.id : 0.01, 
            ...     dot2.id : 0.02
            ... }
            >>> dot_pair_1.couplings[sensor_dot.id] = {
            ...     dot1.id: 0.1, 
            ...     dot2.id: 0.15
            ... }
    """

    quantum_dots: List[QuantumDot]
    sensor_dots: List[SensorDot] = field(default_factory = list)
    barrier_gate: BarrierGate = None
    dot_coupling: float = 0.0
    couplings: Dict[str, Dict[str, float]] = field(default_factory = dict)

    def __post_init__(self): 
        if len(self.sensor_dots) != 0:
            for s_dot in self.sensor_dots:
                if s_dot.id not in self.couplings:
                    self.couplings[s_dot.id] = {
                        self.quantum_dots[0].id: 0.0, 
                        self.quantum_dots[1].id: 0.0
                    }
        
        if self.barrier_gate is not None: 
            if self.barrier_gate.id not in self.couplings: 
                self.couplings[self.barrier_gate.id] = {
                    self.quantum_dots[0].id: 0.0, 
                    self.quantum_dots[1].id: 0.0
                }
