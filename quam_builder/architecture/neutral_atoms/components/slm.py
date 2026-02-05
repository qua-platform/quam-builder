from quam.core import quam_dataclass
from quam.components import SingleChannel
from quam.components import QuantumComponent
from dataclasses import field

@quam_dataclass
class SLM(QuantumComponent):
    name: str
    channel: SingleChannel
    pattern_loaded: bool = field(default=True, init=False)  # preloaded by default

    @QuantumComponent.register_macro
    def enable(self):
        """Trigger the SLM to display the preloaded phase mask."""
        self.channel.current_voltage = 1.0
        if hasattr(self.channel, "offset_parameter"):
            self.channel.offset_parameter(1.0)

    @QuantumComponent.register_macro
    def disable(self):
        """Turn off the SLM."""
        self.channel.current_voltage = 0.0
        if hasattr(self.channel, "offset_parameter"):
            self.channel.offset_parameter(0.0)