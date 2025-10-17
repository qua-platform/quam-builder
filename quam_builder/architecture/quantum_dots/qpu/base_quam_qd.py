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
    
    qubits: Dict[str, AnySpinQubit] = field(default_factory = dict)
    virtual_gate_sets: Dict[str, VirtualGateSet] = field(default_factory = dict)
    capacitance_matrix: List[List[float]] = field(default_factory = list)

    qubit_pairs: Dict[str, AnySpinQubitPair] = field(default_factory=dict)

    quantum_dots: Dict[str, QuantumDot] = field(default_factory = dict)
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

    def create_virtual_gate_set(self, 
                                gate_set_id:str = None, 
                                capacitance_matrix: List[List[float]] = None, 
                                use_pair_couplings: bool = True,
    ) -> None: 
        """
        Create an internal VirtualGateSet to include all the coupled channels in your hardware. 
        Internally creates a mapping of virtual_gates -> physical_gates
        """
        # Set default name for the VirtualGateSet
        if gate_set_id is None: 
            gate_set_id = f"virtual_gate_set_{len(self.virtual_gate_sets.keys())}"

        channel_mapping = {}
        
        # Helper function which takes a dict and extracts a list of physical names and virtual names, while updating the channel_mapping
        def add_gates(items: Dict, get_channel_fn): 
            physical_names = []
            virtual_names = []
            for item in items.values():
                physical_name = f"{item.id}_physical"
                physical_names.append(physical_name)
                virtual_names.append(item.id)
                channel = get_channel_fn(item)
                channel_mapping[physical_name] = channel.get_reference()

            return physical_names, virtual_names

        # Add any qubits to the channel mapping
        physical_qubit_names, virtual_qubit_names = add_gates(self.qubits, lambda q: q.physical_channel)

        # Add any miscellaneous dots to the channel mapping
        physical_dot_names, virtual_dot_names = add_gates(self.quantum_dots, lambda dot: dot.physical_channel)

        def merge_couplings_dicts(base, new):
            """
            Merge the element to qubit couplings with new entries. Resulting dict should be, e.g., 
                {
                    "sensor1" : {
                        "qubit1" : 0.1, 
                        "qubit2" : 0.2, 
                    }, 
                    "barrier1": {
                        "qubit1" : 0.02, 
                        "qubit2" : 0.01, 
                    }, 
                }
            """
            result = defaultdict(dict, base)
            for key, value in new.items():
                result[key].update(value)
            return result

        # Find all the relevant sensor and barrier gates 

        physical_barrier_names, virtual_barrier_names = [], []
        physical_sensor_names, virtual_sensor_names = [], []
        if self.sensor_dots != {}: 
            physical_sensor_names, virtual_sensor_names = add_gates(self.sensor_dots, lambda dot: dot.physical_channel)
        if self.barrier_gates != {}:
            physical_barrier_names, virtual_barrier_names = add_gates(self.barrier_gates, lambda gate: gate)
    
        couplings = {}
        seen_sensors = set(virtual_sensor_names)
        seen_barriers = set(virtual_barrier_names)
        for q_pair in list(self.qubit_pairs.values()): 
            couplings = merge_couplings_dicts(couplings, q_pair.couplings)
            barrier_gate = q_pair.barrier_gate
            if barrier_gate.id not in seen_barriers:
                phys_barrier_name = f"{barrier_gate.id}_physical"
                virtual_barrier_names.append(barrier_gate.id)
                physical_barrier_names.append(phys_barrier_name)

                # Need a .get_reference() here, since the barrier_gate should already be parented (by the QubitPair)
                channel_mapping[phys_barrier_name] = barrier_gate.get_reference()
            for s_dot in q_pair.sensor_dots:
                if s_dot.id not in seen_sensors:
                    seen_sensors.add(s_dot.id)
                    phys_sensor_name = f"{s_dot.id}_physical" 
                    virtual_sensor_names.append(s_dot.id)
                    physical_sensor_names.append(phys_sensor_name)

                    # No need for .get_reference() here, since the sensor dots are in a list
                    channel_mapping[phys_sensor_name] = s_dot.physical_channel.get_reference()

        # Create a full list of all the virtual and physical gate names, mapped correctly
        full_virtual_list = virtual_qubit_names + virtual_dot_names + virtual_sensor_names + virtual_barrier_names 
        full_physical_list = physical_qubit_names + physical_dot_names + physical_sensor_names + physical_barrier_names

        # Instantiate the VirtualGateSet using the channel mapping. Add it to the internal self.virtual_gate_sets dict
        self.virtual_gate_sets[gate_set_id] = VirtualGateSet(id = gate_set_id, channels = channel_mapping)

        # If the user does not include the (cross-capacitance) matrix for very first layer, then assume identity
        if capacitance_matrix is None: 
            capacitance_matrix = np.eye(len(full_virtual_list)).tolist()
        
        # Add first initial layer to map the virtual gates -> underlying physical channels. 
        # This matrix is update-able via a class method
        self.virtual_gate_sets[gate_set_id].add_layer(
            source_gates = full_virtual_list, 
            target_gates = full_physical_list, 
            matrix = capacitance_matrix
        )

        if use_pair_couplings:
            # Add the element-to-qubit couplings
            for gate in couplings:
                for (g, value) in couplings[gate].items():
                    self.update_cross_compensation_element(gate_set_id, gate, g, value)
            
            # Add the qubit-to-qubit couplings
            for q_pair in self.qubit_pairs.values(): 
                self.update_cross_compensation_element(gate_set_id, q_pair.qubit_control.id, q_pair.qubit_target.id, q_pair.dot_coupling)
            
        
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

