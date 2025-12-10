from typing import Optional

from quam.components import SingleChannel
from quam.core import quam_dataclass

__all__ = ["VoltageGate"]


@quam_dataclass
class VoltageGate(SingleChannel):
    """
    A voltage gate is a single channel that can be used to apply a voltage to a quantum dot.

    Attributes:
        attenuation: The attenuation of the voltage gate. Default is zero
        offset_parameter: The optional DC offset of the voltage gate
            Can be e.g. a QDAC channel

    Example:
        >>>
        >>> # Create VoltageGate
        >>> gate = VoltageGate(
        ...     opx_output = (...),
        ...     operations = {...},
        ...     sticky = ...
        ...     )
        >>>
        >>> # Attach e.g. a QCoDeS driver channel to VoltageGate; example shows a QCoDeS driver for QDAC-II
        >>> gate.offset_parameter = QDAC.ch17.dc_constant_V
        >>>
        >>> # Set and return the DC voltage
        >>> gate.offset_parameter(0.1) # Sets 0.1V
        >>> gate.offset_parameter() # Returns 0.1V
    """

    attenuation: float = 0.0
    # current_external_voltage, an attribute to help with serialising the experimental state
    current_external_voltage: Optional[float] = None
    qdac_channel: int = None
    

    def __post_init__(self):
        if hasattr(self.opx_output, "upsampling_mode"): 
            self.opx_output.upsampling_mode = "pulse"
        self._offset_parameter = None
        self.opx_external_ratio: float = 10**(self.attenuation / 20)

    @property
    def physical_channel(self):
        return self

    @property
    def offset_parameter(self):
        return self._offset_parameter

    @offset_parameter.setter
    def offset_parameter(self, value):
        self._offset_parameter = value
        if self.offset_parameter is not None: 
            self.current_external_voltage = self.offset_parameter()
