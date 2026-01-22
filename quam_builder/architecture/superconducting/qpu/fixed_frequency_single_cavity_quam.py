from dataclasses import field
from typing import Dict, ClassVar, Type, List

from quam.core import quam_dataclass

from quam_builder.architecture.superconducting.qubit import FixedFrequencyTransmon, BosonicMode
from quam_builder.architecture.superconducting.qpu.base_quam import BaseQuam


__all__ = ["FixedFrequencyTransmonSingleCavityQuam"]


@quam_dataclass
class FixedFrequencyTransmonSingleCavityQuam(BaseQuam):
    """QUAM composed of fixed frequency transmons and bosonic cavity modes.

    This QPU architecture combines anharmonic transmon qubits with harmonic
    bosonic cavity modes, enabling hybrid quantum systems. Cavities can serve
    as quantum memories, bosonic modes for error correction, or as computational
    resources in hybrid qubit-cavity architectures.

    Attributes:
        qubit_type (ClassVar[Type[FixedFrequencyTransmon]]): The type of the qubits in the QUAM for type hinting.
        cavity_type (ClassVar[Type[BosonicMode]]): The type of the cavities in the QUAM for type hinting.
        qubits (Dict[str, FixedFrequencyTransmon]): A dictionary of qubits composing the QUAM.
        cavities (Dict[str, BosonicMode]): A dictionary of bosonic cavity modes composing the QUAM.
        active_cavity_names (List[str]): A list of active cavity names.

    Methods:
        load: Loads the QUAM from the state.json file.
        active_cavities: Returns the list of active cavities.
    """

    qubit_type: ClassVar[Type[FixedFrequencyTransmon]] = FixedFrequencyTransmon
    cavity_type: ClassVar[Type[BosonicMode]] = BosonicMode

    qubits: Dict[str, FixedFrequencyTransmon] = field(default_factory=dict)
    cavities: Dict[str, BosonicMode] = field(default_factory=dict)
    active_cavity_names: List[str] = field(default_factory=list)

    @property
    def active_cavities(self) -> List[BosonicMode]:
        """Return the list of active cavities."""
        return [self.cavities[c] for c in self.active_cavity_names]

    @classmethod
    def load(cls, *args, **kwargs) -> "FixedFrequencyTransmonSingleCavityQuam":
        return super().load(*args, **kwargs)
