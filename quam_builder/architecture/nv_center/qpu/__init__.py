from typing import Union

from quam_builder.architecture.nv_center.qpu.base_quam import BaseQuamNV
from quam_builder.architecture.nv_center.qpu.nv_center_quam import NVCenterQuam

__all__ = [
    *base_quam.__all__,
    *nv_center_quam.__all__,
]

AnyQuamNV = Union[BaseQuamNV, NVCenterQuam]
