from dataclasses import field
from typing import List, Dict, ClassVar, Optional, Union

from qm import QuantumMachinesManager, QuantumMachine
from qm.octave import QmOctaveConfig
from qm.qua._dsl import _ResultSource
from qm.qua._expressions import QuaVariable
from qm.qua import declare_stream, declare, fixed

from quam.components import FrequencyConverter
from quam.core import QuamRoot, quam_dataclass
from quam.components.octave import Octave
from quam.components.ports import FEMPortsContainer, OPXPlusPortsContainer
from quam.serialisation import JSONSerialiser

from quam_builder.architecture.superconducting.qubit_pair import AnyTransmonPair
from quam_builder.architecture.superconducting.qubit import AnyTransmon

from qualang_tools.results.data_handler import DataHandler

__all__ = ["BaseQuam"]


@quam_dataclass
class BaseQuam(QuamRoot):
    """Example QUAM root component."""

    octaves: Dict[str, Octave] = field(default_factory=dict)
    mixers: Dict[str, FrequencyConverter] = field(default_factory=dict)

    qubits: Dict[str, AnyTransmon] = field(default_factory=dict)
    qubit_pairs: Dict[str, AnyTransmonPair] = field(default_factory=dict)
    wiring: dict = field(default_factory=dict)
    network: dict = field(default_factory=dict)

    active_qubit_names: List[str] = field(default_factory=list)
    active_qubit_pair_names: List[str] = field(default_factory=list)

    ports: Union[FEMPortsContainer, OPXPlusPortsContainer] = None

    _data_handler: ClassVar[DataHandler] = None
    qmm: ClassVar[Optional[QuantumMachinesManager]] = None

    @classmethod
    def get_serialiser(cls) -> JSONSerialiser:
        """Get the serialiser for the QuamRoot class, which is the JSONSerialiser.

        This method can be overridden by subclasses to provide a custom serialiser.
        """
        return JSONSerialiser(content_mapping={"wiring": "wiring.json", "network": "wiring.json"})

    def get_octave_config(self) -> QmOctaveConfig:
        """Return the Octave configuration."""
        octave_config = None
        for octave in self.octaves.values():
            if octave_config is None:
                octave_config = octave.get_octave_config()
        return octave_config

    def connect(self) -> QuantumMachinesManager:
        """Open a Quantum Machine Manager with the credentials ("host" and "cluster_name") as defined in the network file.

        Returns: the opened Quantum Machine Manager.
        """
        settings = dict(
            host=self.network["host"],
            cluster_name=self.network["cluster_name"],
            octave=self.get_octave_config(),
        )
        if "port" in self.network:
            settings["port"] = self.network["port"]
        self.qmm = QuantumMachinesManager(**settings)  # TODO: how to fix this warning?
        return self.qmm

    def calibrate_octave_ports(self, QM: QuantumMachine) -> None:
        """Calibrate the Octave ports for all the active qubits.

        Args:
            QM (QuantumMachine): the running quantum machine.
        """
        from qm.octave.octave_mixer_calibration import NoCalibrationElements

        for name in self.active_qubit_names:
            try:
                self.qubits[name].calibrate_octave(QM)
            except NoCalibrationElements:
                print(f"No calibration elements found for {name}. Skipping calibration.")

    @property
    def active_qubits(self) -> List[AnyTransmon]:
        """Return the list of active qubits."""
        return [self.qubits[q] for q in self.active_qubit_names]

    @property
    def active_qubit_pairs(self) -> List[AnyTransmonPair]:
        """Return the list of active qubits."""
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
    ) -> tuple[
        list[QuaVariable],
        list[_ResultSource],
        list[QuaVariable],
        list[_ResultSource],
        QuaVariable,
        _ResultSource,
    ]:
        """Macro to declare the necessary QUA variables for all qubits"""

        n = declare(int)
        n_st = declare_stream()
        I = [declare(fixed) for _ in range(len(self.qubits))]
        Q = [declare(fixed) for _ in range(len(self.qubits))]
        I_st = [declare_stream() for _ in range(len(self.qubits))]
        Q_st = [declare_stream() for _ in range(len(self.qubits))]
        return I, I_st, Q, Q_st, n, n_st

    def initialize_qpu(self, **kwargs):
        pass
