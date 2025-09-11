from quam.components import SingleChannel
from quam.core import quam_dataclass
from typing import Optional


@quam_dataclass
class VoltageGate(SingleChannel):
    """
    A voltage gate is a single channel that can be used to apply a voltage to a quantum dot.
    """

    attenuation: Optional[float] = None

    def __post_init__(self):
        self._offset_parameter = None

    @property
    def offset_parameter(self):
        return self._offset_parameter

    @offset_parameter.setter
    def offset_parameter(self, value):
        self._offset_parameter = value
