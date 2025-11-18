from typing import Dict, List, Union, TYPE_CHECKING
from dataclasses import field

from quam.core import quam_dataclass, QuamComponent

from quam_builder.tools.voltage_sequence.voltage_sequence import VoltageSequence
from quam_builder.architecture.quantum_dots.components.quantum_dot import QuantumDot
from quam_builder.architecture.quantum_dots.components.sensor_dot import SensorDot
from quam_builder.architecture.quantum_dots.components.barrier_gate import BarrierGate
from quam_builder.architecture.quantum_dots.components.macros import VoltagePointMacroMixin

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["QuantumDotPair"]


@quam_dataclass
class QuantumDotPair(QuamComponent, VoltagePointMacroMixin):

    """
    Class representing a Quantum Dot Pair. 
    Attributes: 
        quantum_dots (List[QuantumDot]): A list of the two QuantumDot instances to be paired. 
        barrier_gate (BarrierGate): The BarrierGate instance between the two QuantumDots.  
        sensor_dots (List[SensorDot]): A list of SensorDot instances coupled to this particular QuantumDot pair. 
        dot_coupling (float): A value representing the coupling strength of the QuantumDot pair.
        points (Dict[str, Dict[str, float]]): A dictionary of instantiated macro points.

    Methods: 
        define_detuning_axis (args: matrix, detuning_axis_name): Adds to the QuantumDotPair Detuning VirtualizationLayer in the VirtualGateSet, expanding the matrix with the input submatrix.
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
        source_gates = [detuning_axis_name]

        # Shape check: if all target gates are properly virtualised, the shape sohuld be 2 x 1
        if len(matrix) != 1: 
            raise ValueError(f"Matrix must have 1 row. Received {len(matrix)}")
        
        if len(matrix[0]) != 2: 
            raise ValueError(f"Matrix must have 2 columns. Received {len(matrix[0])}")

        virtual_gate_set.add_to_layer(
            layer_id = "quantum_dot_pair_detuning_matrix", 
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

    def _get_component_id_for_voltages(self) -> str:
        """
        Override to use the detuning axis for voltage operations on the pair.

        Returns:
            str: The detuning axis name to use for voltage operations
        """
        return self.detuning_axis_name

    # Voltage point macro methods (add_point, step_to_point, ramp_to_point) are now provided by VoltagePointMacroMixin

