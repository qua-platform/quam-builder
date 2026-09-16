from quam.components.channels import IQChannel, MWChannel
from quam.core import quam_dataclass

__all__ = ["CrossResonanceDriveIQ", "CrossResonanceDriveMW"]


@quam_dataclass
class CrossResonanceDriveBase:
    pass


@quam_dataclass
class CrossResonanceDriveIQ(IQChannel, CrossResonanceDriveBase):
    intermediate_frequency: int = "#./inferred_intermediate_frequency"

    @property
    def upconverter_frequency(self):
        """Returns the up-converter/LO frequency in Hz."""
        return self.LO_frequency


@quam_dataclass
class CrossResonanceDriveMW(MWChannel, CrossResonanceDriveBase):
    intermediate_frequency: int = "#./inferred_intermediate_frequency"

    @property
    def upconverter_frequency(self):
        """Returns the up-converter/LO frequency in Hz."""
        return self.opx_output.upconverter_frequency
