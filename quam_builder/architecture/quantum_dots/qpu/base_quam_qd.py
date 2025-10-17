from typing import List, Dict, Union, ClassVar, Optional
from dataclasses import field
import numpy as np
from collections import defaultdict

from qm import QuantumMachinesManager, QuantumMachine
from qm.octave import QmOctaveConfig

from quam.serialisation import JSONSerialiser
from quam.components import Octave, FrequencyConverter
from quam.components import Channel
from quam.components.ports import FEMPortsContainer, OPXPlusPortsContainer
from quam.core import quam_dataclass, QuamRoot, QuamBase

from quam_builder.architecture.quantum_dots.components import (
    VirtualGateSet, 
    QuantumDot, 
    VoltageGate, 
    SensorDot, 
    BarrierGate,
    QuantumDotPair,
)
from quam_builder.architecture.quantum_dots.qubit import AnySpinQubit, LDQubit
from quam_builder.architecture.quantum_dots.qubit_pair import AnySpinQubitPair

__all__ = ["BaseQuamQD"]

@quam_dataclass
class BaseQuamQD(QuamRoot): 
    """
    Example QUAM root component for a Quantum Dot Device

    Attributes: 
        octaves (Dict[str, Octave]): A dictionary of Octave components.
        mixers (Dict[str, FrequencyConverter]): A dictionary of frequency converters.
        qubits (Dict[str, AnySpinQubit]): A dictionary of spin qubits.
        qubit_pairs (Dict[str, AnySpinQubitPair]): A dictionary of spin qubit pairs.
        quantum_dots (Dict[str, QuantumDot]): A dictionary of additional coupled quantum dots to be included in the VirtualGateSet.
        b_field (float): The operating external magnetic field.
        back_gate (VoltageGate): The channel object associated with the back gate.
        wiring (dict): The wiring configuration.
        network (dict): The network configuration.
        active_qubit_names (List[str]): A list of active qubit names.
        active_qubit_pair_names (List[str]): A list of active qubit pair names.
        ports (Union[FEMPortsContainer, OPXPlusPortsContainer]): The ports container.
        _data_handler (ClassVar[DataHandler]): The data handler.
        qmm (ClassVar[Optional[QuantumMachinesManager]]): The Quantum Machines Manager.
    
    Methods: 
        get_serialiser: Get the serialiser for the QuamRoot class, which is the JSONSerialiser.
        get_octave_config: Return the Octave configuration.
        connect: Open a Quantum Machine Manager with the credentials ("host" and "cluster_name") as defined in the network file.
        calibrate_octave_ports: Calibrate the Octave ports for all the active qubits.
        active_qubits: Return the list of active qubits.
        active_qubit_pairs: Return the list of active qubit pairs.
        thermalization_time: Return the longest thermalization time amongst the active qubits.
        declare_qua_variables: Macro to declare the necessary QUA variables for all qubits.
        initialize_qpu: Initialize the QPU with the specified settings.
    """

    physical_channels: Dict[str, Channel] = field(default_factory = list)
    
    qubits: Dict[str, AnySpinQubit] = field(default_factory = dict)
    virtual_gate_sets: Dict[str, VirtualGateSet] = field(default_factory = dict)
    capacitance_matrix: List[List[float]] = field(default_factory = list)

    qubit_pairs: Dict[str, AnySpinQubitPair] = field(default_factory=dict)

    quantum_dots: Dict[str, QuantumDot] = field(default_factory = dict)
    quantum_dot_pairs: Dict[str, QuantumDotPair] = field(default_factory = dict)
    sensor_dots: dict[str, SensorDot] = field(default_factory = dict)
    barrier_gates: dict[str, BarrierGate] = field(default_factory = dict)

    back_gate: VoltageGate = None
    b_field: float = 0

    active_qubit_names: List[str] = field(default_factory=list)
    active_qubit_pair_names: List[str] = field(default_factory=list)

    octaves: Dict[str, Octave] = field(default_factory=dict)
    mixers: Dict[str, FrequencyConverter] = field(default_factory=dict)
    wiring: dict = field(default_factory=dict)
    network: dict = field(default_factory=dict)

    ports: Union[FEMPortsContainer, OPXPlusPortsContainer] = None

    qmm: ClassVar[Optional[QuantumMachinesManager]] = None

    @classmethod
    def get_serialiser(cls) -> JSONSerialiser:
        """Get the serialiser for the QuamRoot class, which is the JSONSerialiser.

        This method can be overridden by subclasses to provide a custom serialiser.
        """
        return JSONSerialiser(
            content_mapping={"wiring": "wiring.json", "network": "wiring.json"}
        )
    
    def register_qubit(self, 
                       qubit_type: str, 
                       ): 
        pass

    def register_quantum_dots(
        self, 
        plunger_channels: List[Channel], 
        gate_set_id: str
    ) -> None: 
        """
        This function creates QuantumDot objects from a list of plunger_channels Channel objects. 

        The name of the QuantumDot will be found in the first layer of the corresponding VirtualGateSet. 

        """
        vgs = self.virtual_gate_sets[gate_set_id]

        for ch in plunger_channels: 
            for key, val in vgs.channels.items(): 
                if val is ch: 
                    physical_name = key
                else: 
                    raise ValueError(f"Channel {ch.id} not associated with VirtualGateSet {gate_set_id}")
                
            virtual_qd_name = vgs.layers[0].source_gates[vgs.layers[0].target_gates.index(physical_name)]
            quantum_dot = QuantumDot(
                id = virtual_qd_name, # Should now be the same as the virtual gate name
                physical_channel = ch.get_reference()
            )

            self.quantum_dots[virtual_qd_name] = quantum_dot

    def register_quantum_dot_pair(
        self,
        
    ) -> None: 
        """
        
        """

        pass

    def create_virtual_gate_set(
            self, 
            included_channels: List[Channel], 
            virtual_gate_names: List[str] = None,
            gate_set_id: str = None, 
            compensation_matrix: List[List[float]] = None
        ) -> None: 
        if gate_set_id is None: 
            gate_set_id = f"virtual_gate_set_{len(self.virtual_gate_sets.keys())}"

        if virtual_gate_names is None: 
            virtual_gate_names = [f"virtual_{i}" for i in range(len(included_channels))]
        physical_gate_names = [f"{ch}_physical" for ch in virtual_gate_names]
        
        # Ensures everything is parented to the Quam machine
        for channel_object in included_channels: 
            if channel_object not in self.physical_channels:
                self.physical_channels[channel_object.id] = (channel_object)

        channel_mapping = dict(zip(physical_gate_names, [ch.get_reference() for ch in included_channels]))

        self.virtual_gate_sets[gate_set_id] = VirtualGateSet(
            id = gate_set_id, 
            channels = channel_mapping
        )

        if compensation_matrix is None: 
            compensation_matrix = np.eye(len(virtual_gate_names)).tolist()

        self.virtual_gate_sets[gate_set_id].add_layer(
            source_gates = virtual_gate_names, 
            target_gates = physical_gate_names, 
            matrix = compensation_matrix
        )
        
    def get_matrix_index(self, virtual_gate_set_name: str, gate_name: str): 
        """ 
        In-case the user would like to find the index of a specified gate in the VirtualGateSet
        """
        # Check for the correct VirtualGateSet in self.virtual_gate_sets
        if virtual_gate_set_name not in self.virtual_gate_sets:
            raise ValueError(f"No such VirtualGateSet. Received {virtual_gate_set_name}")
        
        virtual_gate_set = self.virtual_gate_sets[virtual_gate_set_name]

        if gate_name not in virtual_gate_set.valid_channel_names: 
            raise ValueError(f"Gate name {gate_name} not in VirtualGateSet.")
        
        # Only look in the cross-compensation layer of the VirtualGateSet.
        layer = virtual_gate_set.layers[0]
        if gate_name in layer.source_gates: 
            return layer.source_gates.index(gate_name)
        if gate_name in layer.target_gates:
            return layer.target_gates.index(gate_name)
        
        raise ValueError(
            f"Gate '{gate_name}' exists in the gate set but not in the base capacitance layer. "
            f"Capacitance can only be updated for gates in layer 0: "
            f"physical gates {layer.source_gates} or virtual gates {layer.target_gates}."
        )

    def update_cross_compensation_element(self, virtual_gate_set_name: str, gate1: str, gate2: str, value: float): 
        """
        Updates the cross-compensation value in the bottommost layer of the VirtualGateSet. 

        Args:  
            virtual_gate_set_name (str): The name of the VirtualGateSet in self.virtual_gate_sets.
            gate1 (str): The name of the first virtual or physical gate name. 
            gate2 (str): The name of the second virtual or physical gate name. 
            value (float): The matrix element value.
        """

        gate1_index, gate2_index = self.get_matrix_index(virtual_gate_set_name, gate1), self.get_matrix_index(virtual_gate_set_name, gate2)
        virtual_gate_set = self.virtual_gate_sets[virtual_gate_set_name]

        virtual_gate_set.layers[0].matrix[gate1_index][gate2_index] = value
        virtual_gate_set.layers[0].matrix[gate2_index][gate1_index] = value


    def update_full_cross_compensation(self, compensation_matrix:List[List[float]], virtual_gate_set_name:str = None) -> None: 
        """
        If an already-established full cross-compensation matrix exists, use this method to add.
        Args: 
            compensation_matrix (List[List[float]]): A full cross-compensation matrix to overwrite the existing matrix in the first VirtualGateSet layer
            virtual_gate_set_name (str): The name of the VirtualGateSet in self.virtual_gate_sets. 
        """
        
        if virtual_gate_set_name is not None and virtual_gate_set_name not in self.virtual_gate_sets:
            raise ValueError(f"No such VirtualGateSet. Received {virtual_gate_set_name}")
        if virtual_gate_set_name is None: 
            virtual_gate_set_name = next(iter(self.virtual_gate_sets.keys()))

        self.virtual_gate_sets[virtual_gate_set_name].layers[0].matrix = compensation_matrix
        
    def step_to_voltage(self, voltages:Dict, default_to_zero:bool = False, gate_set_name:str = None) -> None: 
        """
        Input a dict of {qubit_name : voltage}, which will be resolved internally. 
        If default_to_zero = True, then all the unnamed qubit values will be defaulted to zero. 
        If default_to_zero = False, then unnamed qubits will be kept at their last tracked level. 
        """
        if gate_set_name is not None and gate_set_name not in list(self.virtual_gate_sets.keys()):
            raise ValueError("Gate Set not found in Quam")
        if gate_set_name is None: 
            gate_set_name = list(self.virtual_gate_sets.keys())[0]
        new_sequence = self.virtual_gate_sets[gate_set_name].new_sequence()

        actual_voltages = {}
        for name, value in voltages.items(): 
            if name in self.qubits: 
                actual_voltages[self.qubits[name].id] = value
            else: 
                actual_voltages[name] = value

        if not default_to_zero: 
            for qubit in self.qubits.keys(): 
                if qubit in voltages: 
                    continue
                else: 
                    voltages[qubit] = self.qubits[qubit].current_voltage
                    
        new_sequence.step_to_voltages(actual_voltages)

    def connect(self) -> QuantumMachinesManager:
        """Open a Quantum Machine Manager with the credentials ("host" and "cluster_name") as defined in the network file.

        Returns:
            QuantumMachinesManager: The opened Quantum Machine Manager.
        """
        settings = dict(
            host=self.network["host"],
            cluster_name=self.network["cluster_name"],
            octave=self.get_octave_config(),
        )
        if "port" in self.network:
            settings["port"] = self.network["port"]
        self.qmm = QuantumMachinesManager(**settings)
        return self.qmm
    
    def get_octave_config(self) -> QmOctaveConfig:
        """Return the Octave configuration."""
        octave_config = None
        for octave in self.octaves.values():
            if octave_config is None:
                octave_config = octave.get_octave_config()
        return octave_config

    def calibrate_octave_ports(self, QM: QuantumMachine) -> None:
        """Calibrate the Octave ports for all the active qubits.

        Args:
            QM (QuantumMachine): The running quantum machine.
        """
        from qm.octave.octave_mixer_calibration import NoCalibrationElements

        for qubit in self.qubits.values():
            try:
                qubit.calibrate_octave(QM)
            except NoCalibrationElements:
                print(
                    f"No calibration elements found for {qubit.id}. Skipping calibration."
                )

    @property
    def active_qubits(self) -> List[AnySpinQubit]: 
        """Return the list of active qubits"""
        return [self.qubits[q] for q in self.active_qubit_names]
    

    @property 
    def active_qubit_pairs(self) -> List[AnySpinQubitPair]:
        """Return the list of active qubit pairs"""
        return [self.qubits[q] for q in self.active_qubit_pair_names]

    def declare_qua_variables(
        self, 
    ): 
        """
        Macro to declare the necessary QUA variables for all qubits. 

        Args: 
            None at the moment
        """
        pass    

    def initialize_qpu(self, **kwargs):
        """Initialize the QPU with the specified settings."""
        pass

