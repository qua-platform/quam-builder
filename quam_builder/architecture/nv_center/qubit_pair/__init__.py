from typing import Union

from quam_builder.architecture.nv_center.qubit_pair.nv_center_pair import NVCenterPair

__all__ = [
    *nv_center_pair.__all__,
]

AnyNVCenterPair = Union[NVCenterPair]
