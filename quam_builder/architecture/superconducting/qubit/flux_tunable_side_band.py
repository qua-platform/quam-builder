from typing import Union

from quam.core import quam_dataclass

from quam_builder.architecture.superconducting.qubit.flux_tunable_transmon import (
    FluxTunableTransmon,
)
from quam_builder.architecture.superconducting.components.xy_drive import XYDriveIQ, XYDriveMW

__all__ = ["FluxTunableTransmonSideBand"]



@quam_dataclass
class FluxTunableTransmonSideBand(FluxTunableTransmon):
    """
    Example QUAM component for a flux tunable transmon qubit.

    Args:

    """
    sideband1: Union[XYDriveIQ, XYDriveMW] = None
    sideband2: Union[XYDriveIQ, XYDriveMW] = None