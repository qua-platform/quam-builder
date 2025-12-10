from dataclasses import field
from typing import Any

from quam.components.quantum_components import QubitPair
from quam.core import quam_dataclass
from quam_builder.architecture.nv_center.qubit.nv_center_spin import NVCenter

__all__ = ["NVCenterPair"]


@quam_dataclass
class NVCenterPair(QubitPair):
    """Example QUAM component for an NV center qubit pair.

    Attributes:
        id (Union[int, str]): The id of the Transmon pair, used to generate the name.
            Can be a string, or an integer in which case it will add `Channel._default_label`.
        qubit_control (NVCenter): The control qubit of the pair.
        qubit_target (NVCenter): The target qubit of the pair.
        extras (Dict[str, Any]): Additional attributes for the NV center pair.
    """

    id: int | str
    qubit_control: NVCenter = None
    qubit_target: NVCenter = None

    extras: dict[str, Any] = field(default_factory=dict)
