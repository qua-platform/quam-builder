from typing import Union
from quam.core import quam_dataclass
from quam_builder.architecture.superconducting.qubit.base_transmon import BaseTransmon
from quam_builder.architecture.superconducting.components.xy_drive import (
    XYDriveIQ,
    XYDriveMW,
)
__all__ = ["FixedFrequencyTransmon"]


@quam_dataclass
class FixedFrequencyTransmon(BaseTransmon):
    """
    Example QUAM component for a transmon qubit.

    Args:

    """
    xy_edge: Union[XYDriveIQ, XYDriveMW] = None
    pass
