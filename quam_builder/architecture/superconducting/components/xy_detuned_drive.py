from quam.core import quam_dataclass
from quam.components.channels import IQChannel, MWChannel
from quam_builder.architecture.superconducting.components.xy_drive import XYDriveMW, XYDriveIQ


__all__ = ["XYDetunedDriveIQ", "XYDetunedDriveMW"]

@quam_dataclass
class XYDetunedDriveBase:
    xy_RF_frequency: float = None
    xy_intermediate_frequency: float = None
    detuning: float = None


@quam_dataclass
class XYDetunedDriveIQ(XYDriveIQ, XYDetunedDriveBase):
    RF_frequency: float = None
    intermediate_frequency: float = None

    @property
    def inferred_RF_frequency(self) -> float:
        return self.xy_RF_frequency + self.detuning

    @property
    def inferred_intermediate_frequency(self) -> float:
        return self.xy_intermediate_frequency + self.detuning


@quam_dataclass
class XYDetunedDriveMW(XYDriveMW, XYDetunedDriveBase):
    RF_frequency: float = None
    intermediate_frequency: float = None

    @property
    def inferred_RF_frequency(self) -> float:
        return self.xy_RF_frequency + self.detuning

    @property
    def inferred_intermediate_frequency(self) -> float:
        return self.xy_intermediate_frequency + self.detuning
