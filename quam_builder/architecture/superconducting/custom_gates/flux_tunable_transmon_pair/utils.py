from typing import Optional, Union
from quam.components.pulses import Pulse
from quam.components.quantum_components import Qubit

def get_pulse_name(pulse: Pulse) -> str:
    """
    Get the name of the pulse. If the pulse has an id, return it.
    """
    if pulse.id is not None:
        return pulse.id
    elif pulse.parent is not None:
        return pulse.parent.get_attr_name(pulse)
    else:
        raise AttributeError(
            f"Cannot infer id of {pulse} because it is not attached to a parent"
        )

def get_pulse(pulse: Union[Pulse, str], qubit: Optional[Qubit]) -> Pulse:
    if isinstance(pulse, Pulse):
        return pulse
    elif qubit is not None:
        return qubit.get_pulse(pulse)
    else:
        raise ValueError(f"Cannot get pulse {pulse} because qubit is not provided")
