import importlib
import logging
from dataclasses import field
from typing import ClassVar

from qm import QuantumMachine, QuantumMachinesManager
from qm.octave import QmOctaveConfig
from qm.qua import declare, declare_stream, fixed
from qm.qua.type_hints import QuaVariable, StreamType
from quam.components import FrequencyConverter
from quam.components.octave import Octave
from quam.components.ports import FEMPortsContainer, OPXPlusPortsContainer
from quam.core import QuamRoot, quam_dataclass
from quam.serialisation import JSONSerialiser
from quam_builder.architecture.superconducting.qubit import AnyTransmon
from quam_builder.architecture.superconducting.qubit_pair import AnyTransmonPair

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

    octaves: dict[str, Octave] = field(default_factory=dict)
    mixers: dict[str, FrequencyConverter] = field(default_factory=dict)

    qubits: dict[str, AnyTransmon] = field(default_factory=dict)
    qubit_pairs: dict[str, AnyTransmonPair] = field(default_factory=dict)
    wiring: dict = field(default_factory=dict)
    network: dict = field(default_factory=dict)

    active_qubit_names: list[str] = field(default_factory=list)
    active_qubit_pair_names: list[str] = field(default_factory=list)

    ports: FEMPortsContainer | OPXPlusPortsContainer | None = None

    qmm: ClassVar[QuantumMachinesManager | None] = None

    @classmethod
    def get_serialiser(cls) -> JSONSerialiser:
        """Get the serialiser for the QuamRoot class, which is the JSONSerialiser.

        This method can be overridden by subclasses to provide a custom serialiser.
        """
        return JSONSerialiser(content_mapping={"wiring": "wiring.json", "network": "wiring.json"})

    def get_octave_config(self) -> QmOctaveConfig | None:
        """Return the Octave configuration."""
        octave_config = None
        for octave in self.octaves.values():
            if octave_config is None:
                octave_config = octave.get_octave_config()
        return octave_config

    def _is_custom_qmm(self, qmm_class: type) -> bool:
        """Check if the QMM class is a custom QMM.

        Checks if the QMM class is not the default QuantumMachinesManager.

        Args:
            qmm_class: The QMM class to check.

        Returns:
            bool: True if using custom QMM, False if using default
                QuantumMachinesManager.
        """
        return qmm_class is not QuantumMachinesManager

    def _get_default_qmm_settings(self) -> dict:
        """Build connection settings for the default QuantumMachinesManager.

        This method only uses the standard fields (host, cluster_name,
        octave config, port) and completely ignores any `qmm_settings` that
        may be present in the network config.

        Returns:
            dict: Connection settings dictionary with host, cluster_name,
                octave (if available), and port (if specified).

        Raises:
            ValueError: If required network fields (host, cluster_name)
                are missing.
        """
        # Validate required fields
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

        logger.debug("Using default QuantumMachinesManager settings")

        return settings

    def _get_custom_qmm_settings(self) -> dict:
        """Get connection settings for a custom QMM class.

        This method requires `qmm_settings` to be present in the network configuration
        and returns it directly without merging with any default fields.

        Returns:
            dict: Connection settings dictionary from `qmm_settings`.

        Raises:
            ValueError: If `qmm_settings` is not present in network configuration.
        """
        if "qmm_settings" not in self.network:
            raise ValueError(
                "qmm_settings is required for custom QMM but is not "
                "specified in network configuration"
            )

        settings = dict(self.network["qmm_settings"])
        logger.debug("Using custom qmm_settings for connection")

        return settings

    def _get_qmm_class(self) -> type:
        """Resolve and return the QMM class to use for connection.

        The method checks the `use_custom_qmm` flag in the network configuration:
        - If `use_custom_qmm` is True: requires `qmm_class` to be present
        - If `use_custom_qmm` is False: always returns default QuantumMachinesManager
        - If `use_custom_qmm` is undefined: checks if `qmm_class` exists
          - If `qmm_class` exists: uses the custom QMM class
          - If `qmm_class` doesn't exist: uses default QuantumMachinesManager

        Returns:
            type: The QMM class to instantiate.

        Raises:
            ValueError: If qmm_class specification is invalid or missing when required.
            ImportError: If the specified QMM module cannot be imported.
            AttributeError: If the specified QMM class doesn't exist.
        """
        use_custom_qmm = self.network.get("use_custom_qmm")

        # If flag is explicitly False, always use default QMM
        if use_custom_qmm is False:
            return QuantumMachinesManager

        # If flag is True, require qmm_class to be present
        if use_custom_qmm is True:
            if "qmm_class" not in self.network:
                raise ValueError(
                    "use_custom_qmm is True but qmm_class is not specified "
                    "in network configuration"
                )

        # If flag is undefined, check if qmm_class exists
        # If no qmm_class, use default QMM
        if "qmm_class" not in self.network:
            return QuantumMachinesManager

        # Import and return custom QMM class
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
        classes (e.g., CloudQuantumMachinesManager). The QMM class selection is
        controlled by the `use_custom_qmm` flag in the network configuration:

        - If `use_custom_qmm` is True: requires both `qmm_class` and `qmm_settings`
        - If `use_custom_qmm` is False: always uses default QuantumMachinesManager
        - If `use_custom_qmm` is undefined: checks for `qmm_class` presence
          - If `qmm_class` exists: uses custom QMM with `qmm_settings`
          - If `qmm_class` doesn't exist: uses default QuantumMachinesManager

        For the standard QuantumMachinesManager, the following fields are needed:
        - host: The host of the Quantum Machine Manager, e.g. "192.168.1.1"
        - cluster_name: The cluster name of the QM system, e.g. "Cluster_1"
        - port (optional): The port of the Quantum Machine Manager, e.g. 50000
          This is typically not needed.

        For custom QMM classes, `qmm_settings` must be provided with all required
        connection parameters.

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
            is_custom = self._is_custom_qmm(qmm_class)

            # Get settings based on QMM type
            if is_custom:
                settings = self._get_custom_qmm_settings()
            else:
                settings = self._get_default_qmm_settings()

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
            raise ConnectionError(f"Failed to connect to Quantum Machines Manager: {e}") from e

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
                print(f"No calibration elements found for {name}. Skipping calibration.")

    @property
    def active_qubits(self) -> list[AnyTransmon]:
        """Return the list of active qubits."""
        return [self.qubits[q] for q in self.active_qubit_names]

    @property
    def active_qubit_pairs(self) -> list[AnyTransmonPair]:
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
        num_IQ_pairs: int | None = None,
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
        i_values = [declare(fixed) for _ in range(num_IQ_pairs)]
        q_values = [declare(fixed) for _ in range(num_IQ_pairs)]
        i_streams = [declare_stream() for _ in range(num_IQ_pairs)]
        q_streams = [declare_stream() for _ in range(num_IQ_pairs)]
        return i_values, i_streams, q_values, q_streams, n, n_st

    def initialize_qpu(self, **kwargs):
        """Initialize the QPU with the specified settings."""
        pass
