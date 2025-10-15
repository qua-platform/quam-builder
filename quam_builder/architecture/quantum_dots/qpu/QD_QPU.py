from quam.core import quam_dataclass, QuamRoot
from quam.components import Channel
from components import GateSet, VirtualGateSet
from typing import List, Dict
from dataclasses import field
import numpy as np
from components import QuantumDot


__all__ = ["QD_QPU"]


@quam_dataclass
class QD_QPU(QuamRoot): 
    """
    Args: 
        channels: An input mapping of the virtual component name to the associated Channel object
        Example: 
            channels = {"virtual_P1" : VoltageGate(id = "physical_output_1")}
    """
    
    qubits: Dict[str, QuantumDot] = field(default_factory = dict)
    gates_id: str = None
    vitual_gate_set: GateSet = None
    capacitance_matrix: List[List[float]] = field(default_factory = list)

    def __post_init__(self): 
        self.create_virtual_gate_set(id = self.id, qubits = self.qubits, capacitance_matrix=self.capacitance_matrix)

    def create_virtual_gate_set(self, 
                                id:str, 
                                qubits: Dict[str,QuantumDot], 
                                capacitance_matrix: List[List[float]] = None
    ) -> None: 
        """
        Input a channel mapping of {"virtual_name" : Channel}. 
        Internally creates a channel_mapping 
        Ensure that all the coupled gates are included in this channel_mapping
        """
        virtual_gate_names = list(qubits.keys())

        physical_gate_names = []
        channel_mapping = {}
        for q in virtual_gate_names: 
            physical_name = q + "_physical"
            physical_gate_names.append(physical_name)
            channel_mapping[physical_name] = qubits[q].physical_channel
        
        self.virtual_gate_set = VirtualGateSet(id = id, channels = channel_mapping)
        if capacitance_matrix is None: 
            capacitance_matrix = np.eye(len(virtual_gate_names)).tolist()
        self.virtual_gate_set.add_layer(
            source_gates = virtual_gate_names, 
            target_gates = physical_gate_names, 
            matrix = capacitance_matrix
        )
        self.qubit_names = virtual_gate_names

    def update_capacitance_matrix(self, capacitance_matrix:List[List[float]]) -> None: 
        self.virtual_gate_set.layers[0].matrix = capacitance_matrix
        
    def step_to_voltage(self, voltages:Dict, default_to_zero:bool = False) -> None: 
        """
        Input a dict of {qubit_name : voltage}, which will be resolved internally. 
        If default_to_zero = True, then all the unnamed qubit values will be defaulted to zero. 
        If default_to_zero = False, then unnamed qubits will be kept at their last tracked level. 
        """

        new_sequence = self.virtual_gate_set.new_sequence()
        if not default_to_zero: 
            for qubit in self.qubits.keys(): 
                if qubit in voltages: 
                    continue
                else: 
                    voltages[qubit] = self.qubits[qubit].sticky_tracker
                    
        new_sequence.step_to_voltages(voltages)
        






