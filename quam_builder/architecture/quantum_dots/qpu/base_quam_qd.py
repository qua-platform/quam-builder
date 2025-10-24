from typing import List, Dict, Union, ClassVar, Optional, Literal
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
    ReadoutResonatorBase
)
from quam_builder.tools.voltage_sequence import VoltageSequence
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

    physical_channels: Dict[str, Channel] = field(default_factory = dict)
    
    
    qubits: Dict[str, AnySpinQubit] = field(default_factory = dict)
    virtual_gate_sets: Dict[str, VirtualGateSet] = field(default_factory = dict)
    voltage_sequences: Dict[str, VoltageSequence] = field(default_factory=dict)

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
    
    def _get_virtual_gate_set(self, channel: Channel): 
        """Find the internal VirtualGateSet associated with a particular output channel"""
        virtual_gate_set = None
        for vgs in list(self.virtual_gate_sets.values()): 
            if channel in list(vgs.channels.values()): 
                virtual_gate_set = vgs
        if virtual_gate_set is None: 
            raise ValueError(f"Channel {channel.id} not found in any VirtualGateSet")
        return virtual_gate_set
    
    def _get_virtual_name(self, channel: Channel): 
        """Return the name of the virtual gate associated with e particular output channel"""
        vgs_name = None
        for name, vgs in list(self.virtual_gate_sets.items()): 
            if channel in list(vgs.channels.values()):
                vgs_name = name
                break

        if vgs_name is None:
            raise ValueError(f"Channel {channel.id} not found in any VirtualGateSet")
        vgs = self.virtual_gate_sets[vgs_name]

        physical_name = None
        for key, val in vgs.channels.items(): 
            if val is channel: 
                physical_name = key
                break  # Found it, exit loop
        
        if physical_name is None:
            raise ValueError(f"Channel {channel.id} not associated with VirtualGateSet {vgs_name}")
        
        virtual_name = vgs.layers[0].source_gates[vgs.layers[0].target_gates.index(physical_name)]
        return virtual_name

    def reset_voltage_sequence(self, gate_set_id): 
        self.voltage_sequences[gate_set_id] = self.virtual_gate_sets[gate_set_id].new_sequence(track_integrated_voltage=True)
        return

    def register_channel_elements(
        self, 
        plunger_channels: List[Channel], 
        sensor_channels_resonators: Dict[Channel, ReadoutResonatorBase],
        barrier_channels: List[Channel]
    ) -> None:
        self.register_quantum_dots(plunger_channels)
        self.register_barrier_gates(barrier_channels)
        self.register_sensor_dots(sensor_channels_resonators)

    def register_quantum_dots(
        self, 
        plunger_channels: List[Channel], 
    ) -> None: 
        """
        Creates QuantumDot objects from a list of plunger_channels Channel objects. 

        The name of the QuantumDot will be found in the first layer of the corresponding VirtualGateSet. 

        """
        for ch in plunger_channels: 
            virtual_name = self._get_virtual_name(ch)
            quantum_dot = QuantumDot(
                id = virtual_name, # Should now be the same as the virtual gate name
                physical_channel = ch.get_reference(), 
                voltage_sequence = self.voltage_sequences[self._get_virtual_gate_set(ch).id]
            )
            self.quantum_dots[virtual_name] = quantum_dot

    def register_sensor_dots(
        self,
        sensor_channels_resonators: Dict[Channel, ReadoutResonatorBase],
    ) -> None:
        
        for ch, res in sensor_channels_resonators.items(): 
            virtual_name = self._get_virtual_name(ch)
            sensor_dot = SensorDot(
                id = virtual_name, 
                physical_channel = ch.get_reference(), 
                readout_resonator = res,                 
                voltage_sequence = self.voltage_sequences[self._get_virtual_gate_set(ch).id]
                )
            self.sensor_dots[virtual_name] = sensor_dot

    def register_barrier_gates(
        self, 
        barrier_channels: List[Channel]
    ) -> None:
        for ch in barrier_channels: 
            virtual_name = self._get_virtual_name(ch)
            barrier_gate = BarrierGate(
                id = virtual_name, 
                opx_output = ch.opx_output.get_reference(), 
                attenuation = ch.attenuation, 
                voltage_sequence = self.voltage_sequences[self._get_virtual_gate_set(ch).id]
            )
            barrier_gate.offset_parameter = ch.offset_parameter
            self.barrier_gates[virtual_name] = barrier_gate


    def register_quantum_dot_pair(
        self, 
        quantum_dots: List[Channel], 
        sensor_dots: List[Channel], 
        barrier_gate: Channel,
        id:str = None,
        dot_coupling: float = 0.0,
    ) -> None: 
        """
        Creates QuantumDotPair objects given a list of Channels
        Args: 
            quantum_dots (List[QuantumDot]): A list of two Channel objects which are already registered as QuantumDots.

        """

        if len(quantum_dots) != 2: 
            raise ValueError(f"Must be 2 QuantumDot objects. Received {len(quantum_dots)}")
        
        qd_names = [self._get_virtual_name(qd) for qd in quantum_dots]
        for name in qd_names: 
            if name not in self.quantum_dots.keys(): 
                raise ValueError(f"Quantum Dot {name} not registered. Please register first")
        if id is None: 
            id = f"{qd_names[0]}_{qd_names[1]}"
            
        sensor_names = [self._get_virtual_name(qd) for qd in sensor_dots]
        for name in sensor_names: 
            if name not in self.sensor_dots.keys(): 
                raise ValueError(f"Sensor Dot {name} not registered. Please register first")

        barrier_name = self._get_virtual_name(barrier_gate)
        if barrier_name not in self.barrier_gates.keys():
            raise ValueError(f"Barrier Gate {barrier_name} not registered. Please register first")

        quantum_dot_pair = QuantumDotPair(
            id = id,
            quantum_dots = [self.quantum_dots[m] for m in qd_names], 
            barrier_gate = self.barrier_gates[barrier_name], 
            sensor_dots = [self.sensor_dots[n] for n in sensor_names], 
            dot_coupling = dot_coupling
        )

        self.quantum_dot_pairs[id] = quantum_dot_pair

    def register_qubit(self, 
                       quantum_dots: List[str],
                       qubit_type: Literal["loss_divincenzo", "singlet_triplet"] = "loss_divincenzo", 
                       drive_channel: Channel = None
                       ): 
        """Instantiates a qubit based on the associated quantum dot and qubit type"""

        if qubit_type.lower() == "loss_divincenzo": 
            for d in quantum_dots: 
                dot = self.quantum_dots[d] # Assume a single quantum dot for a LD Qubit
                qubit = LDQubit(
                    id = dot.id, 
                    quantum_dot = dot.get_reference(), 
                    drive = drive_channel, 
                )
            
                self.qubits[qubit.id] = qubit
            
    def register_qubit_pair(self, 
                            qubits = []): 
        pass

    def add_point(self, gate_set_id: str, name:str, voltages: Dict, duration: int): 
        return self.virtual_gate_sets[gate_set_id].add_point(name, voltages, duration)

    def create_virtual_gate_set(
            self, 
            virtual_channel_mapping: Dict[str, Channel], 
            gate_set_id: str = None, 
            compensation_matrix: List[List[float]] = None
        ) -> None: 
        if gate_set_id is None: 
            gate_set_id = f"virtual_gate_set_{len(self.virtual_gate_sets.keys())}"

        virtual_gate_names, physical_gate_names = [],[]
        channel_mapping = {}
        for virtual_name, ch in virtual_channel_mapping.items(): 

            # Store list of virtual gate names and physical gate names to ensure correct indexing for the VirtualizationLayer
            virtual_gate_names.append(virtual_name)
            physical_name = f"{virtual_name}_physical"
            physical_gate_names.append(physical_name)

            # Add the channel to self.physical_channels if it does not already exist
            if ch not in list(self.physical_channels.values()): 
                self.physical_channels[ch.id] = (ch)

            # Add to the channel mapping, which (for the VirtualGateSet) maps the physical channel names to the physical channel objects
            channel_mapping[physical_name] = ch.get_reference()
        

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
        self.voltage_sequences[gate_set_id] = self.virtual_gate_sets[gate_set_id].new_sequence(track_integrated_voltage=True)
        
    def get_matrix_index(self, channel): 
        """ 
        In-case the user would like to find the index of a specified gate in the VirtualGateSet
        """
        vgs = self._get_virtual_gate_set(channel)
        virtual_name = self._get_virtual_name(channel)
        index = vgs.layers[0].source_gates.index(virtual_name)

        return vgs, index

    def update_cross_compensation_submatrix(self, virtual_names: List[str], channels: List[Channel], matrix: Union[List[List[float]], np.ndarray]) -> None: 
        """
        Updates the a sub-space of the cross-compensation matrix based on the virtual_names and the associated channels. 
        Does not have to be a square matrix.

        Args:  
            virtual_names (List[str]): A list of the virtual gate names in the sub-space you want to edit. Must be in the same VirtualGateSet
            channels (List[Channel]): The corresponding HW channels that you would like to edit
            matrix (List | np.ndarray): The matrix elements to edit 
        """
        sub = np.asarray(matrix)
        if sub.shape != (len(channels), len(virtual_names)): 
            raise ValueError(f"Sub-matrix shape mismatch: Expected ({len(channels), len(virtual_names)}) but received {sub.shape}")

        # Use the first element in the channels list to find relevant VirtualGateSet. All virtual names and channels should be in the same VirtualGateSet anyway
        vgs = self._get_virtual_gate_set(channels[0])
        source_gates = vgs.layers[0].source_gates

        # Create a mapping of virtual gate : corresponding index in the full matrix. 
        source_index = {name:i for i, name in enumerate(source_gates)}

        missing_virtual_names = [v for v in virtual_names if v not in source_gates]
        if missing_virtual_names: 
            raise ValueError(f"Virtual Gate(s) not in VirtualGateSet {vgs.id}: {missing_virtual_names}")

        full_matrix = vgs.layers[0].matrix

        for subspace_j, v in enumerate(virtual_names): 
            # The corresponding index in the full compensation matrix
            full_matrix_j = source_index[v]

            for subspace_i, ch in enumerate(channels): 
                # Get the virtual name associated with the channel
                virtual_name = self._get_virtual_name(ch)
                # For the first layer, there should be a 1:1 mapping of channel HW to the virtual gate name, so reuse the same indexing method 
                full_matrix_i = source_index[virtual_name]

                # Replace the matrix elemeent 
                full_matrix[full_matrix_i][full_matrix_j] = matrix[subspace_i][subspace_j]

        # Lists should be mutable, but for a sanity check, re-equate the matrix
        vgs.layers[0].matrix = full_matrix


    def update_full_cross_compensation(self, compensation_matrix:List[List[float]], virtual_gate_set_name:str = None) -> None: 
        """
        If an already-calculated full cross-compensation matrix exists, use this method to add.
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
        return [self.qubit_pairs[q] for q in self.active_qubit_pair_names]

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

