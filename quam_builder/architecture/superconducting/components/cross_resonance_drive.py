from quam.components.channels import IQChannel, MWChannel
from quam.core import quam_dataclass

__all__ = ["CrossResonanceDriveIQ", "CrossResonanceDriveMW"]


@quam_dataclass
class CrossResonanceDriveBase:
    """
    QUAM hardware channel for a cross-resonance drive.

    Attributes:
        target_qubit_RF_frequency (float): target qubit's RF frequency.
    """

    target_qubit_RF_frequency: float = None


@quam_dataclass
class CrossResonanceDriveIQ(IQChannel, CrossResonanceDriveBase):
    intermediate_frequency: float = "#./inferred_intermediate_frequency"

    @property
    def upconverter_frequency(self):
        return self.LO_frequency

    @property
    def inferred_intermediate_frequency(self):
        return self.target_qubit_RF_frequency - self.LO_frequency


@quam_dataclass
class CrossResonanceDriveMW(MWChannel, CrossResonanceDriveBase):
    intermediate_frequency: float = "#./inferred_intermediate_frequency"

    @property
    def inferred_intermediate_frequency(self):
        return self.target_qubit_RF_frequency - self.LO_frequency
