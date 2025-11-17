from quam.components.channels import IQChannel, MWChannel
from quam.core import quam_dataclass
from quam_builder.architecture.superconducting.components.xy_drive import XYDriveMW, XYDriveIQ

__all__ = ["ResetIQ", "ResetMW"]


@quam_dataclass
class ResetIQ(XYDriveIQ):
    pass


@quam_dataclass
class ResetMW(XYDriveMW):
    pass
