from typing import List, Dict, Union, ClassVar, Optional
from dataclasses import field
import numpy as np

from qm import QuantumMachinesManager, QuantumMachine
from qm.octave import QmOctaveConfig

from quam.serialisation import JSONSerialiser
from quam.components import Octave, FrequencyConverter
from quam.components import Channel
from quam.components.ports import FEMPortsContainer, OPXPlusPortsContainer
from quam.core import quam_dataclass, QuamRoot

from quam_builder.architecture.quantum_dots.components import GateSet, VirtualGateSet, QuantumDot, VoltageGate
from quam_builder.architecture.quantum_dots.qubit import AnySpinQubit, ld_qubit
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

    quantum_dots: Dict[str, QuantumDot] = None

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
                                use_pair_capacitance: bool = True,
    ) -> None: 
        """
        Create an internal VirtualGateSet to include all the coupled channels in your hardware. 
        Internally creates a mapping of virtual_gates -> physical_gates
        """
        if gate_set_id is None: 
            gate_set_id = f"virtual_gate_set_{len(self.virtual_gate_sets.keys())}"

        # Find all the qubits in self.qubits
        physical_qubit_names, virtual_qubit_names = [], []
        channel_mapping = {}
        for q in list(self.qubits.keys()): 
            physical_name = q + "_physical"
            physical_qubit_names.append(physical_name)
            virtual_qubit_names.append(q)
            channel_mapping[physical_name] = self.qubits[q].physical_channel


        # Find all the barrier gates and sensor dos associated to the qubitpairs
        physical_barrier_names, virtual_barrier_names = [],[]
        physical_sensor_names, virtual_sensor_names = [],[]
        for q_pair in list(self.qubit_pairs.values()): 
            barrier_gate = q_pair.barrier_gate
            
            phys_barrier_name = barrier_gate.id + "_physical"
            virtual_barrier_names.append(barrier_gate.id)
            physical_barrier_names.append(phys_barrier_name)
            channel_mapping[phys_barrier_name] = barrier_gate

            sensor_dots = q_pair.sensor_dots
            for s_dot in sensor_dots:
                if s_dot.id not in virtual_sensor_names:
                    phys_sensor_name = s_dot.id + "_physical"
                    virtual_sensor_names.append(s_dot.id)
                    physical_sensor_names.append(phys_sensor_name)
                    channel_mapping[phys_sensor_name] = s_dot.physical_channel

        # Find any miscellaneous quantum dots (psudo-reservoirs, etc)
        physical_dot_names, virtual_dot_names = [],[]
        for dot in list(self.quantum_dots.keys()): 
            physical_name = dot + "_physical"
            physical_dot_names.append(physical_name)
            virtual_dot_names.append(dot)
            channel_mapping[physical_name] = self.quantum_dots[dot].physical_channel


        full_virtual_list = virtual_qubit_names + virtual_dot_names + virtual_sensor_names + virtual_barrier_names 
        full_physical_list = physical_qubit_names + physical_dot_names + physical_sensor_names + physical_barrier_names

        self.full_virtual_names_list = full_virtual_list
        self.full_physical_names_list = full_physical_list
        
        self.virtual_gate_sets[gate_set_id] = VirtualGateSet(id = gate_set_id, channels = channel_mapping)
        if capacitance_matrix is None: 
            capacitance_matrix = np.eye(len(full_virtual_list)).tolist()


        self.virtual_gate_sets[gate_set_id].add_layer(
            source_gates = full_virtual_list, 
            target_gates = full_physical_list, 
            matrix = capacitance_matrix
        )
        

    def update_capacitance_matrix(self, capacitance_matrix:List[List[float]], gate_set_name:str = None) -> None: 
        if gate_set_name is not None and gate_set_name not in list(self.virtual_gate_sets.keys()):
            raise ValueError("Gate Set not found in Quam")
        if gate_set_name is None: 
            gate_set_name = list(self.virtual_gate_sets.keys())[0]

        self.virtual_gate_sets[gate_set_name].layers[0].matrix = capacitance_matrix
        
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
        if not default_to_zero: 
            for qubit in self.qubits.keys(): 
                if qubit in voltages: 
                    continue
                else: 
                    voltages[qubit] = self.qubits[qubit].current_voltage
                    
        new_sequence.step_to_voltages(voltages)

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

