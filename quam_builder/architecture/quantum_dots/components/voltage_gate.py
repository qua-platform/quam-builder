from typing import Any, Callable, Optional, Union

from quam.components import SingleChannel
from quam.core import quam_dataclass

from .readout_transport import ANY_READOUT_TRANSPORT
from .readout_resonator import ANY_READOUT_RESONATOR

from .dac_spec import DacSpec, QdacSpec

__all__ = ["VoltageGate"]


class _OffsetParameterTrackingProxy:
    """Wraps a callable offset (e.g. QCoDeS Parameter) to sync ``current_external_voltage`` on each call."""

    __slots__ = ("_gate", "_inner")

    def __init__(self, gate: "VoltageGate", inner: Callable[..., Any]) -> None:
        self._gate = gate
        self._inner = inner

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        result = self._inner(*args, **kwargs)
        gate = self._gate

        if args and not kwargs and len(args) == 1:
            v = args[0]
            if isinstance(v, (int, float)):
                gate.current_external_voltage = float(v)
        elif not args and not kwargs:
            if isinstance(result, (int, float)):
                gate.current_external_voltage = float(result)

        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._inner!r})"


@quam_dataclass
class VoltageGate(SingleChannel):
    """
    A voltage gate is a single channel that can be used to apply a voltage to a quantum dot.

    Attributes:
        attenuation: The attenuation of the voltage gate. Default is zero.
        settling_time: The settling time of the voltage gate in ns. The value will be cast to an integer multiple of 4ns
            automatically. Default is None.
        offset_parameter: The optional DC offset of the voltage gate
            Can be e.g. a QDAC channel. Callable values are wrapped so that
            ``gate.offset_parameter(v)`` and ``gate.offset_parameter()`` update
            ``current_external_voltage`` when a numeric value is written or read.

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
        if value is None:
            self._offset_parameter = None
        elif isinstance(value, _OffsetParameterTrackingProxy):
            self._offset_parameter = _OffsetParameterTrackingProxy(self, value._inner)
            self.current_external_voltage = self._offset_parameter()
        elif callable(value):
            self._offset_parameter = _OffsetParameterTrackingProxy(self, value)
            self.current_external_voltage = self._offset_parameter()
        else:
            self._offset_parameter = value

    def settle(self):
        """Wait for the voltage bias to settle"""
        if self.settling_time is not None:
            self.wait(int(self.settling_time) // 4 * 4)
