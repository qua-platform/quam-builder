from typing import Dict, List, Union
from dataclasses import field

from quam.core import quam_dataclass
from quam.components import Channel

from quam_builder.architecture.quantum_dots.components import QuantumDot, SensorDot

@quam_dataclass
class QuantumDotPair:


    quantum_dots: Dict[str, QuantumDot]
    barrier: Channel

    




