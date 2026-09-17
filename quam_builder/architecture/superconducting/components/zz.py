from quam.components.channels import IQChannel, MWChannel
from quam.core import quam_dataclass

__all__ = ["ZZDriveIQ", "ZZDriveMW"]


@quam_dataclass
class ZZDriveBase:
    detuning: int = None


@quam_dataclass
class ZZDriveIQ(IQChannel, ZZDriveBase):
    intermediate_frequency: float = "#./inferred_intermediate_frequency"

    @property
    def upconverter_frequency(self):
        """Returns the up-converter/LO frequency in Hz."""
        return self.LO_frequency

    @property
    def inferred_intermediate_frequency(self):
        return self.RF_frequency - self.LO_frequency + self.detuning


@quam_dataclass
class ZZDriveMW(MWChannel, ZZDriveBase):
    intermediate_frequency: int = "#./inferred_intermediate_frequency"

    @property
    def upconverter_frequency(self):
        """Returns the up-converter/LO frequency in Hz."""
        return self.opx_output.upconverter_frequency

    @property
    def inferred_intermediate_frequency(self):
        return self.RF_frequency - self.LO_frequency + self.detuning
