from quam.core import quam_dataclass
from quam.components.quantum_components import QuantumComponent
from quam_builder.architecture.superconducting.components.xy_drive import (
    XYDriveIQ,
    XYDriveMW,
)
from qm.qua import align, wait
from quam_builder.tools.power_tools import get_output_power_iq_channel
from typing import Union

__all__ = ["TWPA"]


@quam_dataclass
class TWPA(QuantumComponent):
    """
    QUAM component for a Traveling Wave Parametric Amplifier (TWPA).

    Attributes:
        gain (float): gain in dB to set
        snr_improvement: measured or targeted SNR improvement
        saturation_power: saturation power of the TWPA
        dispersive_feature: 
    """
    id: Union[int, str]
    pump: Union[XYDriveIQ, XYDriveMW] = None
    gain: float = None
    snr_improvement: float = None
    saturation_power: float = None
    dispersive_feature: float = None

    def get_output_power(self, operation, Z=50) -> float:
        """
        Calculate the output power in dBm of the specified operation.

        Parameters:
            operation (str): The name of the operation to retrieve the amplitude.
            Z (float): The impedance in ohms. Default is 50 ohms.

        Returns:
            float: The output power in dBm.

        The function calculates the output power based on the amplitude of the specified operation and the gain of the
        frequency up-converter. It converts the amplitude to dBm using the specified impedance.
        """
        return get_output_power_iq_channel(self, operation, Z)

    
    @property
    def name(self):
        """The name of the TWPA"""
        return self.id if isinstance(self.id, str) else f"q{self.id}"

   
    # def align(self, other = None):
    #     channels = [self.pump.name, self.resonator.name, self.z.name]

    #     if other is not None:
    #         channels += [other.xy.name, other.resonator.name, other.z.name]

    #     align(*channels)

    # def wait(self, duration):
    #     wait(duration, self.xy.name, self.z.name, self.resonator.name)
