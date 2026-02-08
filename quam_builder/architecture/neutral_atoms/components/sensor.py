from quam.core import quam_dataclass
from quam.components import QuantumComponent, DigitalOutputChannel

@quam_dataclass
class Sensor(QuantumComponent):
    channel: DigitalOutputChannel 
    
    @property
    def name(self) -> str:
        return self.id
    