from quam.core import quam_dataclass
from quam.components import SingleChannel, DigitalOutputChannel
from quam_builder.architecture.neutral_atoms.components.tweezer_driver import TweezerDriver
from quam.components import QuantumComponent
from dataclasses import field

@quam_dataclass
class SLM(TweezerDriver):
    channel: DigitalOutputChannel
    frequency_to_move: float  # Frequency shift to move the tweezer position
    pattern_loaded: bool = field(default=True, init=False)  # preloaded by default  
    
    @property
    def name(self) -> str:
        return self.id
    
    @QuantumComponent.register_macro
    def enable(self):
        """Trigger the SLM to display the preloaded phase mask."""
        self.channel.current_voltage = 1.0

    @QuantumComponent.register_macro
    def disable(self):
        """Turn off the SLM."""
        self.channel.current_voltage = 0.0