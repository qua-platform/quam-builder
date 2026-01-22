from dataclasses import field
from typing import Dict, ClassVar, Type

from quam.core import quam_dataclass

from quam_builder.architecture.superconducting.qubit import FixedFrequencyTransmon, BosonicMode
from quam_builder.architecture.superconducting.qpu.base_quam import BaseQuam


__all__ = ["FixedFrequencyTransmonSingleCavityQuam"]


@quam_dataclass
class FixedFrequencyTransmonSingleCavityQuam(BaseQuam):
    """QUAM composed of fixed frequency transmons and bosonic cavity modes.

    This QPU architecture combines anharmonic transmon qubits with harmonic
    bosonic cavity modes, enabling hybrid quantum systems.

    Attributes:
        qubit_type (ClassVar[Type[FixedFrequencyTransmon]]): The type of the qubits in the QUAM for type hinting.
        cavity_type (ClassVar[Type[BosonicMode]]): The type of the cavities in the QUAM for type hinting.
        qubits (Dict[str, FixedFrequencyTransmon]): A dictionary of qubits composing the QUAM.
        cavities (Dict[str, BosonicMode]): A dictionary of bosonic cavity modes composing the QUAM.

    Methods:
        load: Loads the QUAM from the state.json file.
    """

    qubit_type: ClassVar[Type[FixedFrequencyTransmon]] = FixedFrequencyTransmon
    cavity_type: ClassVar[Type[BosonicMode]] = BosonicMode

    qubits: Dict[str, FixedFrequencyTransmon] = field(default_factory=dict)
    cavities: Dict[str, BosonicMode] = field(default_factory=dict)

    @classmethod
    def load(cls, *args, **kwargs) -> "FixedFrequencyTransmonSingleCavityQuam":
        return super().load(*args, **kwargs)
