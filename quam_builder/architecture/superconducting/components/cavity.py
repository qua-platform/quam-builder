from quam.components.channels import IQChannel, MWChannel
from quam.core import quam_dataclass
from quam_builder.architecture.superconducting.components.xy_drive import XYDriveMW, XYDriveIQ

__all__ = ["CavityIQ", "CavityMW"]


@quam_dataclass
class CavityIQ(XYDriveIQ):
    pass


@quam_dataclass
class CavityMW(XYDriveMW):
    pass