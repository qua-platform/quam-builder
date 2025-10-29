from typing import Dict, List, Union, TYPE_CHECKING
from dataclasses import field

from quam.core import quam_dataclass, QuamComponent

from quam_builder.tools.voltage_sequence.voltage_sequence import VoltageSequence
from quam_builder.architecture.quantum_dots.components.quantum_dot import QuantumDot
from quam_builder.architecture.quantum_dots.components.sensor_dot import SensorDot
from quam_builder.architecture.quantum_dots.components.barrier_gate import BarrierGate

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["QuantumDotPair"]


@quam_dataclass
class QuantumDotPair(QuamComponent):

    """
    Class representing a Quantum Dot Pair. 
    Attributes: 
        quantum_dots (List[QuantumDot]): A list of the two QuantumDot instances to be paired. 
        barrier_gate (BarrierGate): The BarrierGate instance between the two QuantumDots.  
        sensor_dots (List[SensorDot]): A list of SensorDot instances coupled to this particular QuantumDot pair. 
        dot_coupling (float): A value representing the coupling strength of the QuantumDot pair.
        points (Dict[str, Dict[str, float]]): A dictionary of instantiated macro points.

    Methods: 
        define_detuning_axis (args: matrix, detuning_axis_name): Adds a VirtualizationLayer onto the VirtualGateSet to define a detuning axis on the virtualized dot axes, using input matrix.
        go_to_detuning: In a simultaneous block, registers a dict input to the VoltageSequence to step or ramp the detuning to specified voltage. 
        step_to_detuning: Step the voltage to the specified detuning value. Can only be used after the detuning axis is defined. 
        ramp_to_detuning: Ramp the voltage to the specified detuning value. Can only be used after the detuning axis is defined. 
        add_point: Adds a point macro to the associated VirtualGateSet. Also registers said point in the internal points attribute. Can accept qubit names 
        step_to_point: Steps to a pre-defined point in the internal points dict. 
        ramp_to_point: Ramps to a pre-defined point in the internal points dict. 
    """
    id: str = None
    quantum_dots: List[QuantumDot]
    sensor_dots: List[SensorDot] = field(default_factory = list)
    barrier_gate: BarrierGate = None
    dot_coupling: float = 0.0

    detuning_axis_name: str = ""
    points: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def __post_init__(self): 
        if isinstance(self.quantum_dots[0], str): 
            return 
        if len(self.quantum_dots) != 2: 
            raise ValueError(f"Number of QuantumDots in QuantumDotPair must be 2. Received {len(self.quantum_dots)} QuantumDots")
        if self.id is None: 
            self.id = f"{self.quantum_dots[0].id}_{self.quantum_dots[1].id}"

        if self.quantum_dots[0].voltage_sequence is not self.quantum_dots[1].voltage_sequence: 
            raise ValueError("Quantum Dots not part of same VoltageSequence")
        
        self.detuning_axis_name = f"{self.id}_epsilon"

    @property
    def voltage_sequence(self) -> VoltageSequence: 
        return self.quantum_dots[0].voltage_sequence
    
    @property 
    def machine(self) -> "BaseQuamQD":
        return self.quantum_dots[0].machine
        
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
        """To be used in a simultaneous block to step/ramp detuning to specified value. Can only be used after define_detuning_axis."""
        return self.voltage_sequence.step_to_voltages({self.detuning_axis_name: voltage}, duration = duration)
    
    def step_to_detuning(self, voltage: float, duration:int = 16) -> None: 
        """Steps the detuning to the specified value. Can only be used after define_detuning_axis."""
        return self.voltage_sequence.step_to_voltages({self.detuning_axis_name: voltage}, duration = duration)
    
    def ramp_to_detuning(self, voltage:float, ramp_duration: int, duration:int = 16): 
        """Ramps the detuning to the specified value. Can only be used after define_detuning_axis."""
        return self.voltage_sequence.step_to_voltages({self.detuning_axis_name: voltage}, duration = duration, ramp_duration = ramp_duration)

    def add_point(self, point_name:str, voltages: Dict[str, float], duration: int = 16, replace_existing_point: bool = False) -> None: 
        """
        Method to add point to the VirtualGateSet for the quantum dot pair.

        Args: 
            point_name (str): The name of the point in the VirtualGateSet
            voltages (Dict[str, float]): A dictionary of the associated voltages. This will NOT be able to read qubit names. 
            duration (int): The duration which to hold the point. 
            replace_existing_point (bool): If the point_name is the same as a previously added point, choose whether to replace old point. Will raise an error if False. 
        """

        gate_set = self.voltage_sequence.gate_set
        existing_points = gate_set.get_macros()
        name_in_sequence = f"{self.id}_{point_name}"
        if name_in_sequence in existing_points and not replace_existing_point: 
            raise ValueError(f"Point name {point_name} already exists for quantum dot pair {self.id}. If you would like to replace, please set replace_existing_point = True")
        self.points[point_name] = voltages
        gate_set.add_point(
            name = name_in_sequence, 
            voltages = voltages, 
            duration = duration
        )
        
    def step_to_point(self, point_name: str, duration:int = 16) -> None: 
        """Step to a point registered for the quantum dot pair"""
        if point_name not in self.points: 
            raise ValueError(f"Point {point_name} not in registered points: {list(self.points.keys())}")
        name_in_sequence = f"{self.id}_{point_name}"
        return self.voltage_sequence.step_to_point(name = name_in_sequence, duration = duration)
    
    def ramp_to_point(self, point_name: str, ramp_duration:int,  duration:int = 16) -> None: 
        """Ramp to a point registered for the quantum dot pair"""
        if point_name not in self.points: 
            raise ValueError(f"Point {point_name} not in registered points: {list(self.points.keys())}")
        name_in_sequence = f"{self.id}_{point_name}"
        return self.voltage_sequence.ramp_to_point(name = name_in_sequence, duration = duration, ramp_duration=ramp_duration)

