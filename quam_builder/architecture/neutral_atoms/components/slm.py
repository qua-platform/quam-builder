from quam.core import quam_dataclass
from quam_builder.architecture.neutral_atoms.components.tweezer_driver import TweezerDriver
from quam.components import QuantumComponent
from dataclasses import field

@quam_dataclass
class SLM(TweezerDriver):
    channel_name: str  # Name of the registered SingleChannel (avoids parent conflict)
    frequency_to_move: float  # Frequency shift to move the tweezer position
    pattern_loaded: bool = field(default=True, init=False)  # preloaded by default

    @property
    def name(self) -> str:
        return self.id

    @property
    def channel(self):
        """Resolve the channel by name from the QPU."""
        return self.parent.parent.get_channel(self.channel_name)

    @QuantumComponent.register_macro
    def on(self):
        """Trigger the SLM by playing a pulse with digital marker ON."""
        self.channel.play("slm_on")
        self.parent.parent.align(elements=[self])

    @QuantumComponent.register_macro
    def off(self):
        """Turn off the SLM by playing a pulse without digital marker."""
        self.channel.play("slm_off")
        self.parent.parent.align(elements=[self])
