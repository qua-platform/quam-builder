from typing import Dict

from dataclasses import dataclass , field
from quam.core import QuamRoot, quam_dataclass , QuantumComponent
from qm import qua , program


from quam.components import SingleChannel
from quam.components.channels import Channel
from quam.components.pulses import SquarePulse

@quam_dataclass
class  BaseQuamNA(QuamRoot):
    channel : SingleChannel
    #channels: list[SingleChannel]


    def set_voltage(self, voltage: float):
        """
        Set the voltage of the channel.

        Args:
            voltage: voltage value to set
        """
        if hasattr(self.channel, "offset_parameter") and self.channel.offset_parameter is not None:
            self.channel.offset_parameter(voltage)
        self.channel.current_voltage = voltage  # keep track internally


    @QuantumComponent.register_macro
    def global_h(self, region: str, amplitude: float = 0.5, length: int = 40):
        """
        Apply a global Hadamard-like π/2 pulse to all qubits in the region.

        Args:
            region: Name of the region containing qubits
            amplitude: Amplitude of the square pulse
            length: Pulse length in samples
            axis_angle: IQ rotation of the pulse (radians)
        """

        # Create the square pulse
        h_pulse = SquarePulse(
            amplitude=amplitude,
            length=length,
        )

        # Play it on the OPX channel associated with this region
        # Assume you have a mapping from region -> channel(s)
        channels = self.get_channels_for_region(region)

        for ch in channels:
            ch.play(h_pulse)