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
    ReadoutResonatorBase
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
    
    def _get_virtual_gate_set(self, channel: Channel): 
        virtual_gate_set = None
        for vgs in self.virtual_gate_sets.values(): 
            if channel in vgs.channels.values(): 
                virtual_gate_set = vgs
        if virtual_gate_set is None: 
            raise ValueError(f"Channel {channel.id} not found in any VirtualGateSet")
        return virtual_gate_set
    
    def _get_virtual_name(self, channel: Channel): 
        vgs_name = None
        for name, vgs in self.virtual_gate_sets.items(): 
            if channel in vgs.channels.values():
                vgs_name = name
                break

        if vgs_name is None:
            raise ValueError(f"Channel {channel.id} not found in any VirtualGateSet")
        vgs = self.virtual_gate_sets[vgs_name]

        for key, val in vgs.channels.items(): 
            if val is channel: 
                physical_name = key
            else: 
                raise ValueError(f"Channel {channel.id} not associated with VirtualGateSet {vgs_name}")
            
        virtual_name = vgs.layers[0].source_gates[vgs.layers[0].target_gates.index(physical_name)]
        return virtual_name

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
                physical_channel = ch.get_reference()
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
                physical_channel = ch, 
                readout_resonator = res
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
                opx_output = ch.opx_output, 
                offset_parameter = ch.offset_parameter,
                attenuation = ch.attenuation
            )
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
                       qubit_type: str, 
                       ): 
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
        
    def get_matrix_index(self, channel): 
        """ 
        In-case the user would like to find the index of a specified gate in the VirtualGateSet
        """
        vgs = self._get_virtual_gate_set(channel)
        virtual_name = self._get_virtual_name(channel)
        index = vgs.layers[0].source_gates.index(virtual_name)

        return vgs, index

    def update_cross_compensation_element(self, ch1: Channel, ch2: Channel, value: float): 
        """
        Updates the cross-compensation value in the bottommost layer of the VirtualGateSet. 

        Args:  
            ch1 (Channel): Hardware channel 1. 
            ch2 (Channel): Hardware Channel 2.
            value (float): The matrix element value.
        """
        vgs1, gate1_index = self.get_matrix_index(ch1)
        vgs2, gate2_index = self.get_matrix_index(ch2)

        if vgs1 is not vgs2: 
            raise ValueError("Channels not in the same VirtualGateSet.")

        vgs1.layers[0].matrix[gate1_index][gate2_index] = value
        vgs1.layers[0].matrix[gate2_index][gate1_index] = value


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

