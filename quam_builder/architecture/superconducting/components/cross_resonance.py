from quam.core import quam_dataclass
from quam.components.channels import IQChannel, MWChannel

__all__ = ["CrossResonanceIQ", "CrossResonanceMW"]


@quam_dataclass
class CrossResonanceBase:
    """
    Example QUAM component for a cross resonance gate.

    Attributes:
        target_qubit_RF_frequency (float): target qubit's frequency.
    """

    target_qubit_RF_frequency: float = None
    drive_amplitude_scaling: float = 1.0
    drive_phase: float = 0.0
    cancel_amplitude_scaling: float = 0.0
    cancel_phase: float = 0.0


@quam_dataclass
class CrossResonanceIQ(IQChannel, CrossResonanceBase):
    @property
    def upconverter_frequency(self):
        return self.LO_frequency

    @property
    def inferred_intermediate_frequency(self):
        return self.target_qubit_RF_frequency - self.LO_frequency


@quam_dataclass
class CrossResonanceMW(MWChannel, CrossResonanceBase):
    @property
    def inferred_intermediate_frequency(self):
        return self.target_qubit_RF_frequency - self.LO_frequency

    @property
    def upconverter_frequency(self):
        return self.opx_output.upconverter_frequency

    @property
    def inferred_RF_frequency(self):
        return self.upconverter_frequency + self.inferred_intermediate_frequency
