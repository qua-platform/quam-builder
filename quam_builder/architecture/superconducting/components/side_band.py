from quam.components.channels import IQChannel, MWChannel
from quam.core import quam_dataclass
from quam_builder.architecture.superconducting.components.xy_drive import XYDriveMW, XYDriveIQ

__all__ = ["SideBandIQ", "SideBandMW"]


@quam_dataclass
class SideBandIQ(XYDriveIQ):
    pass


@quam_dataclass
class SideBandMW(XYDriveMW):
    pass