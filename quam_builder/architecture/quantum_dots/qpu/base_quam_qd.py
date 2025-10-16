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
    virtual_gate_sets: Dict[str, GateSet] = field(default_factory = dict)
    capacitance_matrix: List[List[float]] = field(default_factory = list)

    qubit_pairs: Dict[str, AnySpinQubitPair] = field(default_factory=dict)

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
                                capacitance_matrix: List[List[float]] = None
    ) -> None: 
        """
        Create an internal VirtualGateSet to include all the coupled gates in your hardware. 
        Internally creates a mapping of virtual_gates -> physical_gates
        """
        if gate_set_id is None: 
            gate_set_id = f"virtual_gate_set_{len(self.virtual_gate_sets.keys())}"

        
        physical_gate_names, virtual_gate_names = [], []
        channel_mapping = {}
        for q in self.qubits.keys(): 
            physical_name = q + "_physical"
            physical_gate_names.append(physical_name)
            virtual_gate_names.append(q)
            channel_mapping[physical_name] = self.qubits[q].physical_channel

        self.qubit_names = virtual_gate_names


        
        
        self.virtual_gate_set = VirtualGateSet(id = gate_set_id, channels = channel_mapping)
        if capacitance_matrix is None: 
            capacitance_matrix = np.eye(len(virtual_gate_names)).tolist()
        self.virtual_gate_set.add_layer(
            source_gates = virtual_gate_names, 
            target_gates = physical_gate_names, 
            matrix = capacitance_matrix
        )
        

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

