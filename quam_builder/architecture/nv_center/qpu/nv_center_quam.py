from dataclasses import field
from typing import ClassVar

from quam.core import quam_dataclass
from quam_builder.architecture.nv_center.qpu.base_quam import BaseQuamNV
from quam_builder.architecture.nv_center.qubit import NVCenter
from quam_builder.architecture.nv_center.qubit_pair import NVCenterPair

__all__ = ["NVCenterQuam", "NVCenter", "NVCenterPair"]


@quam_dataclass
class NVCenterQuam(BaseQuamNV):
    """Example of a QUAM composed of fixed frequency transmons.

    Attributes:
        qubit_type (ClassVar[Type[NVCenter]]): The type of the qubits in the QUAM for type hinting.
        qubit_pair_type (ClassVar[Type[NVCenterPair]]): The type of the qubit pairs in the QUAM for type hinting.
        qubits (Dict[str, NVCenter]): A dictionary of qubits composing the QUAM.
        qubit_pairs (Dict[str, NVCenterPair]): A dictionary of qubit pairs composing the QUAM.

    Methods:
        load: Loads the QUAM from the state.json file.
    """

    qubit_type: ClassVar[type[NVCenter]] = NVCenter
    qubit_pair_type: ClassVar[type[NVCenterPair]] = NVCenterPair

    qubits: dict[str, NVCenter] = field(default_factory=dict)
    qubit_pairs: dict[str, NVCenterPair] = field(default_factory=dict)

    @classmethod
    def load(cls, *args, **kwargs) -> "NVCenterQuam":
        return super().load(*args, **kwargs)
