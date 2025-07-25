from typing import Literal, Union

import numpy as np
from qm.qua import Cast, assign, broadcast, declare, fixed, while_

from quam.components.macro import QubitMacro, QubitPairMacro
from quam.components.pulses import Pulse, ReadoutPulse
from quam.core import quam_dataclass
from quam.utils.qua_types import QuaVariableBool, QuaVariableFloat, QuaVariableInt

__all__ = ["CZGate"]


def get_pulse_name(pulse: Pulse) -> str:
    """
    Get the name of the pulse. If the pulse has an id, return it.
    """
    if pulse.id is not None:
        return pulse.id
    elif pulse.parent is not None:
        return pulse.parent.get_attr_name(pulse)
    else:
        raise AttributeError(f"Cannot infer id of {pulse} because it is not attached to a parent")


@quam_dataclass
class CZGate(QubitPairMacro):
    flux_pulse_control: Union[Pulse, str]
    coupler_flux_pulse: Pulse = None

    pre_wait: int = 4

    phase_shift_control: float = 0.0
    phase_shift_target: float = 0.0

    @property
    def coupler(self):  # -> "TunableCoupler":
        return self.qubit_pair.coupler

    @property
    def flux_pulse_control_label(self) -> str:
        pulse = (
            self.qubit_control.get_pulse(self.flux_pulse_control)
            if isinstance(self.flux_pulse_control, str)
            else self.flux_pulse_control
        )
        return get_pulse_name(pulse)

    @property
    def coupler_flux_pulse_label(self) -> str:
        pulse = (
            self.coupler.get_pulse(self.coupler_flux_pulse)
            if isinstance(self.coupler_flux_pulse, str)
            else self.coupler_flux_pulse
        )
        return get_pulse_name(pulse)

    def apply(
        self,
        *,
        amplitude_scale=None,
        phase_shift_control=None,
        phase_shift_target=None,
        **kwargs,
    ) -> None:
        self.qubit_pair.qubit_control.z.play(
            self.flux_pulse_control_label,
            validate=False,
            amplitude_scale=amplitude_scale,
        )

        if self.coupler_flux_pulse is not None:
            self.qubit_pair.coupler.play(self.coupler_flux_pulse_label, validate=False)

        self.qubit_pair.align()
        if phase_shift_control is not None:
            self.qubit_pair.qubit_control.xy.frame_rotation_2pi(phase_shift_control)
        elif np.abs(self.phase_shift_control) > 1e-6:
            self.qubit_pair.qubit_control.xy.frame_rotation_2pi(self.phase_shift_control)
        if phase_shift_target is not None:
            self.qubit_pair.qubit_target.xy.frame_rotation_2pi(phase_shift_target)
        elif np.abs(self.phase_shift_target) > 1e-6:
            self.qubit_pair.qubit_target.xy.frame_rotation_2pi(self.phase_shift_target)

        self.qubit_pair.qubit_control.xy.play("x180", amplitude_scale=0.0, duration=4)
        self.qubit_pair.qubit_target.xy.play("x180", amplitude_scale=0.0, duration=4)
        self.qubit_pair.align()
