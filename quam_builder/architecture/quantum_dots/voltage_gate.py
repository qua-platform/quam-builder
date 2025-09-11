from quam.components import SingleChannel
from quam.core import quam_dataclass


@quam_dataclass
class VoltageGate(SingleChannel):
    """
    A voltage gate is a single channel that can be used to apply a voltage to a quantum dot.

    Attributes:
        attenuation: The attenuation of the voltage gate. Default is zero
        offset_parameter: The optional DC offset of the voltage gate
            Can be e.g. a QDAC channel
    """

    attenuation: float = 0.0

    def __post_init__(self):
        self._offset_parameter = None

    @property
    def offset_parameter(self):
        return self._offset_parameter

    @offset_parameter.setter
    def offset_parameter(self, value):
        self._offset_parameter = value
