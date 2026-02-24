from quam.core import quam_dataclass
from quam_builder.architecture.neutral_atoms.components.tweezer_driver import TweezerDriver
from quam.components import SingleChannel, DigitalOutputChannel
from quam.components import QuantumComponent
from quam.components.pulses import SquarePulse

@quam_dataclass
class AOD(TweezerDriver):
    channel_x: SingleChannel  # X-axis channel; stores a QUAM reference string e.g. "#/channels/ch1"
    channel_y: SingleChannel  # Y-axis channel; stores a QUAM reference string e.g. "#/channels/ch2"
    frequency_to_move: float  # Frequency shift to move the tweezer position
    offset_frequency: float = 0.0  # Offset frequency for calibration

    @property
    def name(self) -> str:
        return self.id

    @QuantumComponent.register_macro
    def enable(self):
        """Enable the AOD driver."""
        self.channel_x.current_voltage = 1.0
        if hasattr(self.channel_x, "offset_parameter"):
            self.channel_x.offset_parameter(1.0)

    @QuantumComponent.register_macro
    def disable(self):
        """Disable the AOD driver."""
        self.channel_x.current_voltage = 0.0
        if hasattr(self.channel_x, "offset_parameter"):
            self.channel_x.offset_parameter(0.0)

    @QuantumComponent.register_macro
    def move(self, target, amplitude: float = 5, length: int = 1):
        """
        Move the tweezer to a new target position.
        Args:
            amplitude: Amplitude of the square pulse
            length: Pulse length in samples
        """
        self.channel_x.play("h_pulse")
        self.channel_y.play("h_pulse")