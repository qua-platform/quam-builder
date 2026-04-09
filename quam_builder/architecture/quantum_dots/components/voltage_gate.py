from typing import Any, Callable, Dict, Optional, Union

from quam.components import Channel, SingleChannel
from quam.core import quam_dataclass

from .readout_transport import ANY_READOUT_TRANSPORT
from .readout_resonator import ANY_READOUT_RESONATOR

from .dac_spec import DacSpec, QdacSpec

__all__ = ["VoltageGate"]


@quam_dataclass
class VoltageGate(SingleChannel):
    """
    A voltage gate is a single channel that can be used to apply a voltage to a quantum dot.

    Attributes:
        attenuation: The attenuation of the voltage gate. Default is zero.
        settling_time: The settling time of the voltage gate in ns. The value will be cast to an integer multiple of 4ns
            automatically. Default is None.
        offset_parameter: The optional DC offset of the voltage gate
            Can be e.g. a QDAC channel.
        opx_output: When ``None``, the gate is **QDAC-only** (no OPX/LF analog port). QUA config then omits
            ``singleInput``; use :attr:`dac_spec` / external drivers for DC.

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

    opx_output: Any = None
    attenuation: float = 0.0
    settling_time: float = None
    # current_external_voltage, an attribute to help with serialising the experimental state
    current_external_voltage: Optional[float] = None
    dac_spec: DacSpec = None
    readout: Union[ANY_READOUT_RESONATOR, ANY_READOUT_TRANSPORT] = None

    def __post_init__(self):
        super().__post_init__()
        self._offset_parameter = None
        self.opx_external_ratio: float = 10 ** (-self.attenuation / 20)

    @property
    def physical_channel(self):
        return self

    @property
    def qdac_spec(self):
        if self.dac_spec is not None and isinstance(self.dac_spec, QdacSpec):
            return self.dac_spec

    @property
    def offset_parameter(self):
        return self._offset_parameter

    @offset_parameter.setter
    def offset_parameter(self, value):
        self._offset_parameter = value
        if callable(self._offset_parameter):
            self.current_external_voltage = self._offset_parameter()

    def settle(self):
        """Wait for the voltage bias to settle"""
        if self.settling_time is not None:
            self.wait(int(self.settling_time) // 4 * 4)

    def apply_to_config(self, config: Dict[str, dict]) -> None:
        """Skip OPX ``singleInput`` when this gate has no OPX analog port (external / QDAC-only DC)."""
        if self.opx_output is None:
            Channel.apply_to_config(self, config)
            return
        super().apply_to_config(config)

    def set_dc_offset(self, offset):  # noqa: ANN001 — match SingleChannel API
        """Raise for QDAC-only gates; OPX has no DC line to offset."""
        if self.opx_output is None:
            raise RuntimeError(
                "VoltageGate has no OPX analog output (QDAC-only wiring); "
                "cannot use set_dc_offset on the OPX. Control DC via dac_spec / external DAC."
            )
        super().set_dc_offset(offset)
