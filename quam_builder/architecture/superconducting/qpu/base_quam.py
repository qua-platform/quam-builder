from dataclasses import field
from typing import List, Dict, ClassVar, Optional, Union
import importlib
import logging

from qm import QuantumMachinesManager, QuantumMachine
from qm.octave import QmOctaveConfig
from qm.qua.type_hints import QuaVariable, StreamType
from qm.qua import declare_stream, declare, fixed

from quam.components import FrequencyConverter
from quam.core import QuamRoot, quam_dataclass
from quam.components.octave import Octave
from quam.components.ports import FEMPortsContainer, OPXPlusPortsContainer
from quam.serialisation import JSONSerialiser

from quam_builder.architecture.superconducting.qubit_pair import AnyTransmonPair
from quam_builder.architecture.superconducting.qubit import AnyTransmon

logger = logging.getLogger(__name__)

__all__ = ["BaseQuam"]


@quam_dataclass
class BaseQuam(QuamRoot):
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
        # _data_handler (ClassVar[DataHandler]): The data handler. # Unused
        qmm (Optional[QuantumMachinesManager]): The Quantum Machines Manager.

    Methods:
        get_serialiser: Get the serialiser for the QuamRoot class.
        get_octave_config: Return the Octave configuration.
        connect: Open a Quantum Machine Manager with network credentials.
        calibrate_octave_ports: Calibrate Octave ports for active qubits.
        active_qubits: Return the list of active qubits.
        active_qubit_pairs: Return the list of active qubit pairs.
        depletion_time: Return longest depletion time amongst active qubits.
        thermalization_time: Return longest thermalization time.
        declare_qua_variables: Declare necessary QUA variables for qubits.
        initialize_qpu: Initialize the QPU with specified settings.
    """

    octaves: Dict[str, Octave] = field(default_factory=dict)
    mixers: Dict[str, FrequencyConverter] = field(default_factory=dict)

    qubits: Dict[str, AnyTransmon] = field(default_factory=dict)
    qubit_pairs: Dict[str, AnyTransmonPair] = field(default_factory=dict)
    wiring: dict = field(default_factory=dict)
    network: dict = field(default_factory=dict)

    active_qubit_names: List[str] = field(default_factory=list)
    active_qubit_pair_names: List[str] = field(default_factory=list)

    ports: Optional[Union[FEMPortsContainer, OPXPlusPortsContainer]] = None

    qmm: ClassVar[Optional[QuantumMachinesManager]] = None

    @classmethod
    def get_serialiser(cls) -> JSONSerialiser:
        """Get the serialiser for the QuamRoot class, which is the JSONSerialiser.

        This method can be overridden by subclasses to provide a custom serialiser.
        """
        return JSONSerialiser(
            content_mapping={"wiring": "wiring.json", "network": "wiring.json"}
        )

    def get_octave_config(self) -> Optional[QmOctaveConfig]:
        """Return the Octave configuration."""
        octave_config = None
        for octave in self.octaves.values():
            if octave_config is None:
                octave_config = octave.get_octave_config()
        return octave_config

    def _get_connection_settings(self, qmm_class: type) -> dict:
        """Prepare connection settings for the QMM.

        Args:
            qmm_class: The QMM class being used for connection.

        Returns:
            dict: Connection settings dictionary.

        Raises:
            ValueError: If required network fields are missing.
        """
        if "qmm_settings" in self.network:
            settings = dict(self.network["qmm_settings"])
            logger.debug("Using custom qmm_settings for connection")

            return settings

        # Build default settings from network configuration
        required_fields = ["host", "cluster_name"]
        for field_name in required_fields:
            if field_name not in self.network:
                raise ValueError(f"Required network field '{field_name}' is missing")

        settings = {
            "host": self.network["host"],
            "cluster_name": self.network["cluster_name"],
        }

        # Add octave config if available
        octave_config = self.get_octave_config()
        if octave_config is not None:
            settings["octave"] = octave_config

        # Add optional port
        if "port" in self.network:
            settings["port"] = self.network["port"]

        logger.debug(f"Using default settings for {qmm_class.__name__}")

        return settings

    def _get_qmm_class(self) -> type:
        """Resolve and return the QMM class to use for connection.

        Returns:
            type: The QMM class to instantiate.

        Raises:
            ValueError: If qmm_class specification is invalid.
            ImportError: If the specified QMM module cannot be imported.
            AttributeError: If the specified QMM class doesn't exist.
        """
        # Use default QMM class if no custom class specified
        if "qmm_class" not in self.network:
            return QuantumMachinesManager

        qmm_path = self.network["qmm_class"]
        if not isinstance(qmm_path, str) or not qmm_path.strip():
            raise ValueError(f"Invalid qmm_class specification: {qmm_path}")

        try:
            # Split module path and class name
            if "." not in qmm_path:
                raise ValueError(f"qmm_class must include module path: {qmm_path}")

            module_path, class_name = qmm_path.rsplit(".", 1)
            logger.debug(f"Importing QMM class: {class_name} from {module_path}")

            # Import module and get class
            module = importlib.import_module(module_path)
            qmm_class = getattr(module, class_name)

            # Verify it's a callable class
            if not callable(qmm_class):
                raise ValueError(f"qmm_class {qmm_path} is not a callable class")

            return qmm_class

        except ImportError as e:
            raise ImportError(f"Failed to import module '{module_path}': {e}") from e
        except AttributeError as e:
            raise AttributeError(
                f"Class '{class_name}' not found in module '{module_path}': {e}"
            ) from e

    def connect(self) -> QuantumMachinesManager:
        """Open a Quantum Machine Manager with credentials from network config.

        The method supports both standard QuantumMachinesManager and custom QMM
        classes (e.g., CloudQuantumMachinesManager). Connection parameters can be
        specified either through 'qmm_settings' for full control or through
        individual fields.

        For the standard QuantumMachinesManager, the following fields are needed:
        - host: The host of the Quantum Machine Manager, e.g. "192.168.1.1"
        - cluster_name: The cluster name of the QM system, e.g. "Cluster_1"
        - port (optional): The port of the Quantum Machine Manager, e.g. 50000
          This is typically not needed.

        Returns:
            QuantumMachinesManager: The opened Quantum Machine Manager.

        Raises:
            ValueError: If network configuration is missing or invalid.
            ImportError: If the specified QMM class cannot be imported.
            AttributeError: If the specified QMM class doesn't exist.
            ConnectionError: If connection to the QMM fails.
        """
        # Validate network configuration exists
        if not self.network:
            raise ValueError(
                "Network configuration is missing. Please set the 'network' attribute."
            )

        # Resolve QMM class and prepare connection settings
        try:
            qmm_class = self._get_qmm_class()
            settings = self._get_connection_settings(qmm_class)

            # Attempt to create and connect QMM
            host = settings.get("host", "unknown host")
            logger.info(f"Connecting to {qmm_class.__name__} at {host}")
            self.qmm = qmm_class(**settings)

            return self.qmm

        except TypeError as e:
            raise ConnectionError(
                f"Failed to initialize {qmm_class.__name__} with provided settings: {e}"
            ) from e
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to Quantum Machines Manager: {e}"
            ) from e

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
    def active_qubits(self) -> List[AnyTransmon]:
        """Return the list of active qubits."""
        return [self.qubits[q] for q in self.active_qubit_names]

    @property
    def active_qubit_pairs(self) -> List[AnyTransmonPair]:
        """Return the list of active qubit pairs."""
        return [self.qubit_pairs[q] for q in self.active_qubit_pair_names]

    @property
    def depletion_time(self) -> int:
        """Return the longest depletion time amongst the active qubits."""
        return max(q.resonator.depletion_time for q in self.active_qubits)

    @property
    def thermalization_time(self) -> int:
        """Return the longest thermalization time amongst the active qubits."""
        return max(q.thermalization_time for q in self.active_qubits)

    def declare_qua_variables(
        self,
        num_IQ_pairs: Optional[int] = None,
    ) -> tuple[
        list[QuaVariable],
        list[StreamType],
        list[QuaVariable],
        list[StreamType],
        QuaVariable,
        StreamType,
    ]:
        """Macro to declare the necessary QUA variables for all qubits.

        Args:
            num_IQ_pairs (Optional[int]): Number of IQ pairs (I and Q variables) to declare.
                If None, it defaults to the number of qubits in `self.qubits`.

        Returns:
            tuple: A tuple containing lists of QUA variables and streams.
        """
        if num_IQ_pairs is None:
            num_IQ_pairs = len(self.qubits)

        n = declare(int)
        n_st = declare_stream()
        I = [declare(fixed) for _ in range(num_IQ_pairs)]
        Q = [declare(fixed) for _ in range(num_IQ_pairs)]
        I_st = [declare_stream() for _ in range(num_IQ_pairs)]
        Q_st = [declare_stream() for _ in range(num_IQ_pairs)]
        return I, I_st, Q, Q_st, n, n_st

    def initialize_qpu(self, **kwargs):
        """Initialize the QPU with the specified settings."""
        pass
