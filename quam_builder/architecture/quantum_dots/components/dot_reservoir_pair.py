from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.components import VoltagePointMacroMixin

@quam_dataclass
class DotReservoirPair(VoltagePointMacroMixin): 
    """
    Class for a quantum dot and reservoir pair. Used for Elzerman readout
    """
    pass