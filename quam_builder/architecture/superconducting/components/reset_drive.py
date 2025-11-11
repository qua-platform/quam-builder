from quam.components.channels import IQChannel, MWChannel
from quam.core import quam_dataclass

__all__ = ["ResetIQ", "ResetMW"]


@quam_dataclass
class ResetBase:
    target_qubit_LO_frequency: int = None
    target_qubit_IF_frequency: int = None
    detuning: int = None


@quam_dataclass
class ResetIQ(IQChannel, ResetBase):

    @property
    def upconverter_frequency(self):
        return self.LO_frequency

    @property
    def inferred_intermediate_frequency(self):
        return self.target_qubit_LO_frequency + self.target_qubit_IF_frequency - self.LO_frequency + self.detuning


@quam_dataclass
class ResetMW(MWChannel, ResetBase):
    @property
    def inferred_intermediate_frequency(self):
        return self.target_qubit_LO_frequency + self.target_qubit_IF_frequency - self.LO_frequency + self.detuning

    @property
    def upconverter_frequency(self):
        return self.opx_output.upconverter_frequency
