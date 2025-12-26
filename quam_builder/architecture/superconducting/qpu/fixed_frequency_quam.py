from dataclasses import field
from typing import Dict, ClassVar, Type

from quam.core import quam_dataclass

from quam_builder.architecture.superconducting.qubit import FixedFrequencyTransmon
from quam_builder.architecture.superconducting.qubit_pair import (
    FixedFrequencyTransmonPair,
)
from quam_builder.architecture.superconducting.qpu.base_quam import BaseQuam


__all__ = ["FixedFrequencyQuam", "FixedFrequencyTransmon", "FixedFrequencyTransmonPair"]


@quam_dataclass
class FixedFrequencyQuam(BaseQuam):
    """Example of a QUAM composed of fixed frequency transmons.

    Attributes:
        qubit_type (ClassVar[Type[FixedFrequencyTransmon]]): The type of the qubits in the QUAM for type hinting.
        qubit_pair_type (ClassVar[Type[FixedFrequencyTransmonPair]]): The type of the qubit pairs in the QUAM for type hinting.
        qubits (Dict[str, FixedFrequencyTransmon]): A dictionary of qubits composing the QUAM.
        qubit_pairs (Dict[str, FixedFrequencyTransmonPair]): A dictionary of qubit pairs composing the QUAM.

    Methods:
        load: Loads the QUAM from the state.json file.
    """

    qubit_type: ClassVar[Type[FixedFrequencyTransmon]] = FixedFrequencyTransmon
    qubit_pair_type: ClassVar[Type[FixedFrequencyTransmonPair]] = (
        FixedFrequencyTransmonPair
    )

    qubits: Dict[str, FixedFrequencyTransmon] = field(default_factory=dict)
    qubit_pairs: Dict[str, FixedFrequencyTransmonPair] = field(default_factory=dict)

    @classmethod
    def load(cls, *args, **kwargs) -> "FixedFrequencyQuam":
        return super().load(*args, **kwargs)
