from typing import Dict, List, Union
from dataclasses import field

from quam.core import quam_dataclass

from quam_builder.tools.voltage_sequence.voltage_sequence import VoltageSequence
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
    """
    id: str = None
    quantum_dots: List[QuantumDot]
    sensor_dots: List[SensorDot] = field(default_factory = list)
    barrier_gate: BarrierGate = None
    dot_coupling: float = 0.0

    detuning_axis_name: str = "epsilon"

    voltage_sequence: VoltageSequence = None

    def __post_init__(self): 
        if len(self.quantum_dots) != 2: 
            raise ValueError(f"Number of QuantumDots in QuantumDotPair must be 2. Received {len(self.quantum_dots)} QuantumDots")
        if self.id is None: 
            self.id = f"{self.quantum_dots[0].id}_{self.quantum_dots[1].id}"

        if self.quantum_dots[0].voltage_sequence is not self.quantum_dots[1].voltage_sequence: 
            raise ValueError("Quantum Dots not part of same VoltageSequence")
        
        self.voltage_sequence = self.quantum_dots[0].voltage_sequence

        
    def define_detuning_axis(self, matrix: List[List[float]], detuning_axis_name: str = None) -> None: 
        
        # If no name is given, ensure that it is the default
        if detuning_axis_name is None: 
            detuning_axis_name = self.detuning_axis_name

        # Ensure that the detuning axis name held in object is consistent
        self.detuning_axis_name = detuning_axis_name

        virtual_gate_set = self.voltage_sequence.gate_set

        # Should be the correct virtual axes in the first layer of the VirtualGateSet
        target_gates = [qd.id for qd in self.quantum_dots]
        source_gates = [detuning_axis_name, f"{detuning_axis_name}_companion"]

        virtual_gate_set.add_layer(
            target_gates = target_gates, 
            source_gates = source_gates, 
            matrix = matrix
        )
    
    def go_to_detuning(self, voltage: float, duration:int = 16) -> None: 
        return self.voltage_sequence.step_to_voltages({self.detuning_axis_name: voltage}, duration = duration)
    
    def step_to_detuning(self, voltage: float, duration:int = 16) -> None: 
        return self.voltage_sequence.step_to_voltages({self.detuning_axis_name: voltage}, duration = duration)
    
    def ramp_to_detuning(self, voltage:float, ramp_duration: int, duration:int = 16): 
        return self.voltage_sequence.step_to_voltages({self.detuning_axis_name: voltage}, duration = duration, ramp_duration = ramp_duration)

