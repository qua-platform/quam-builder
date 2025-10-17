from dataclasses import field
from typing import List, Dict, ClassVar, Optional, Union

from qm import QuantumMachinesManager, QuantumMachine
from qm.octave import QmOctaveConfig
from qm.qua.type_hints import QuaVariable, StreamType
from qm.qua import declare_stream, declare, fixed

from quam.components import FrequencyConverter
from quam.core import QuamRoot, quam_dataclass
from quam.components.octave import Octave
from quam.components.ports import FEMPortsContainer, OPXPlusPortsContainer
from quam.serialisation import JSONSerialiser

from quam_builder.architecture.nv_center.qubit_pair import NVCenterPair
from quam_builder.architecture.nv_center.qubit import NVCenter

from qualang_tools.results.data_handler import DataHandler

__all__ = ["BaseQuamNV"]


@quam_dataclass
class BaseQuamNV(QuamRoot):
    """Example QUAM root component.

    Attributes:
        octaves (Dict[str, Octave]): A dictionary of Octave components.
        mixers (Dict[str, FrequencyConverter]): A dictionary of frequency converters.
        qubits (Dict[str, AnyTransmon]): A dictionary of transmon qubits.
        qubit_pairs (Dict[str, AnyTransmonPair]): A dictionary of transmon qubit pairs.
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
        declare_qua_variables: Macro to declare the necessary QUA variables for all qubits.
        initialize_qpu: Initialize the QPU with the specified settings.
    """

    octaves: Dict[str, Octave] = field(default_factory=dict)
    mixers: Dict[str, FrequencyConverter] = field(default_factory=dict)

    qubits: Dict[str, NVCenter] = field(default_factory=dict)
    qubit_pairs: Dict[str, NVCenterPair] = field(default_factory=dict)
    wiring: dict = field(default_factory=dict)
    network: dict = field(default_factory=dict)

    active_qubit_names: List[str] = field(default_factory=list)
    active_qubit_pair_names: List[str] = field(default_factory=list)

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

    def get_octave_config(self) -> QmOctaveConfig:
        """Return the Octave configuration."""
        octave_config = None
        for octave in self.octaves.values():
            if octave_config is None:
                octave_config = octave.get_octave_config()
        return octave_config

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

    def calibrate_octave_ports(self, QM: QuantumMachine) -> None:
        """Calibrate the Octave ports for all the active qubits.

        Args:
            QM (QuantumMachine): The running quantum machine.
        """
        from qm.octave.octave_mixer_calibration import NoCalibrationElements

        for name in self.active_qubit_names:
            try:
                self.qubits[name].calibrate_octave(QM)
            except NoCalibrationElements:
                print(
                    f"No calibration elements found for {name}. Skipping calibration."
                )

    @property
    def active_qubits(self) -> List[NVCenter]:
        """Return the list of active qubits."""
        return [self.qubits[q] for q in self.active_qubit_names]

    @property
    def active_qubit_pairs(self) -> List[NVCenterPair]:
        """Return the list of active qubit pairs."""
        return [self.qubit_pairs[q] for q in self.active_qubit_pair_names]

    def declare_qua_variables(self) -> tuple[
        list[QuaVariable],
        list[StreamType],
        list[QuaVariable],
        list[StreamType],
        QuaVariable,
        StreamType,
    ]:
        """Macro to declare the necessary QUA variables for all qubits.

        Returns:
            tuple: A tuple containing lists of QUA variables and streams.
        """
        raise NotImplementedError("This function is not yet implemented.")

    def initialize_qpu(self, **kwargs):
        """Initialize the QPU with the specified settings."""
        # set laser dc offset
        for qubit in self.qubits:
            if qubit.laser.power:
                qubit.laser.power.set_dc_offset(qubit.laser.power.dc_voltage)
