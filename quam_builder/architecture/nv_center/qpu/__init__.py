from . import base_quam, nv_center_quam
from .base_quam import BaseQuamNV
from .nv_center_quam import NVCenterQuam

__all__ = [
    *base_quam.__all__,
    *nv_center_quam.__all__,
]

AnyQuamNV = BaseQuamNV | NVCenterQuam
