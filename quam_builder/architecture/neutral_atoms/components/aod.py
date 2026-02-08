from quam.core import quam_dataclass
from quam_builder.architecture.neutral_atoms.components.tweezer_driver import TweezerDriver
from quam.components import SingleChannel, DigitalOutputChannel
from quam.components import QuantumComponent
from quam.components.pulses import SquarePulse

@quam_dataclass
class AOD(TweezerDriver):
    channels: (SingleChannel, SingleChannel)  # (X channel, Y channel)
    frequency_to_move: float  # Frequency shift to move the tweezer position
    offset_frequency: float = 0.0  # Offset frequency for calibration

    @property
    def name(self) -> str:
        return self.id

    @QuantumComponent.register_macro
    def enable(self):
        """Enable the AOD driver."""
        self.channel.current_voltage = 1.0
        if hasattr(self.channel, "offset_parameter"):
            self.channel.offset_parameter(1.0)

    @QuantumComponent.register_macro
    def disable(self):
        """Disable the AOD driver."""
        self.channel.current_voltage = 0.0
        if hasattr(self.channel, "offset_parameter"):
            self.channel.offset_parameter(0.0)
    
    @QuantumComponent.register_macro
    def move(self, target, amplitude: float = 5, length: int = 1):
        """
        Move the tweezer to a new target position.
        Args:
            amplitude: Amplitude of the square pulse
            length: Pulse length in samples
        """
        # Create the square pulse
        h_pulse = SquarePulse(
            amplitude=amplitude,
            length=length,
        )
        # Create the square pulse
        for ch in self.channels:
            ch.play(h_pulse)