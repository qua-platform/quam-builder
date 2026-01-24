from typing import Union

from quam.core import quam_dataclass

from quam_builder.architecture.superconducting.qubit.flux_tunable_side_band import (
    FluxTunableTransmonSideBand,
)
from quam_builder.architecture.superconducting.components.xy_drive import XYDriveIQ, XYDriveMW


__all__ = ["FluxTunableTransmonCavity"]




@quam_dataclass
class FluxTunableTransmonCavity(FluxTunableTransmonSideBand):
    """
    Example QUAM component for a flux tunable transmon qubit.

    Args:

    """
    alice: Union[XYDriveIQ, XYDriveMW] = None
    bob: Union[XYDriveIQ, XYDriveMW] = None