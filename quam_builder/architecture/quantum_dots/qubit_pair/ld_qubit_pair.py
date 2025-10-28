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

    points: Dict[str, Dict[str, float]] = field(default_factory = dict)

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


    def add_point(self, point_name:str, voltages: Dict[str, float], duration: int = 16, replace_existing_point: bool = False) -> None: 
        """
        Add a point macro to the VirtualGateSet associated with the qubit pair. 
        
        Args: 
            point_name (str): The name of the point macro
            voltages (Dict[str, float]): A dictionary of voltages to enter into the VirtualGateSet. This can include qubit names and QD names, as well as 
                                            any virtualised axis in the VirtualGateSet. Internally, qubit names are converted to the names of the associated quantum dots. 
            duration (int): The duration which to hold the point. 
            replace_existing_point (bool): If the point_name is the same as a previously added point, choose whether to replace old point. Will raise an error if False. 
        """
        name_in_sequence = f"{self.id}_{point_name}"
        # In-case there are any qubit names in the input dictionary, this must be mapped to the correct quantum dot gate name in the VirtualGateSet
        processed_voltages = {}
        qubit_mapping = self.parent.parent.qubits
        for gate_name, voltage in voltages.items(): 
            if gate_name in qubit_mapping: 
                gate_name = qubit_mapping[gate_name].id
            processed_voltages[gate_name] = voltage

        gate_set = self.voltage_sequence.gate_set
        existing_points = gate_set.get_macros()

        if name_in_sequence in existing_points and not replace_existing_point: 
            raise ValueError(f"Point name {point_name} already exists for qubit {self.id}. If you would like to replace, please set replace_existing_point = True")
        self.points[point_name] = voltages
        gate_set.add_point(
            name = name_in_sequence, 
            voltages = processed_voltages, 
            duration = duration
        )
        
    def step_to_point(self, point_name: str, duration:int = 16) -> None: 
        """Step to a point registered for the qubit"""
        if point_name not in self.points: 
            raise ValueError(f"Point {point_name} not in registered points: {list(self.points.keys())}")
        name_in_sequence = f"{self.id}_{point_name}"
        return self.voltage_sequence.step_to_point(name = name_in_sequence, duration = duration)
    
    def ramp_to_point(self, point_name: str, ramp_duration:int,  duration:int = 16) -> None: 
        """Ramp to a point registered for the qubit"""
        if point_name not in self.points: 
            raise ValueError(f"Point {point_name} not in registered points: {list(self.points.keys())}")
        name_in_sequence = f"{self.id}_{point_name}"
        return self.voltage_sequence.ramp_to_point(name = name_in_sequence, duration = duration, ramp_duration=ramp_duration)
