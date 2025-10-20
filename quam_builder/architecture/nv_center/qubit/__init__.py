from typing import Union

from quam_builder.architecture.nv_center.qubit.nv_center_spin import NVCenter

__all__ = [
    *nv_center_spin.__all__,
]

AnyNVCenter = Union[NVCenter]
