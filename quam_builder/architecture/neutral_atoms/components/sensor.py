from quam.core import quam_dataclass
from quam.components import QuantumComponent, DigitalOutputChannel

@quam_dataclass
class Sensor(QuantumComponent):
    channel: DigitalOutputChannel 
    
    @property
    def name(self) -> str:
        return self.id

    @QuantumComponent.register_macro
    def trigger(self):
        self.channel.current_voltage = 1.0
    
