from typing import Union

import numpy as np
from qualang_tools.units import unit
from quam.components import pulses

from quam_builder.architecture.nv_center.qubit import NVCenter
from quam_builder.architecture.nv_center.qubit_pair import NVCenterPair

# Class containing tools to help handling units and conversions.
u = unit(coerce_to_integer=True)

def add_Square_pulses(
    nv_center: NVCenter,
    amplitude: float,
    length: int,
    digital_marker: str = None,
):
    """Adds a set of Square pulses to a nv_center qubit and sets the gate shape as 'Square'.
    The function will create the 6 operations corresponding to the set of single qubit gates:
    ["x180_Square", "x90_Square", "-x90_Square", "y180_Square", "y90_Square", "-y90_Square"].

    The specified parameters are the parameters for x180 and will be propagated to the other gates, except for the
    amplitude which is halved for the "x90", "-x90", "y90" and "-y90" gates.

    Args:
        nv_center (NVCenter): The nv_center qubit to which the pulses will be added.
        amplitude (float): The amplitude of the pulses in Volts.
        length (int): The length of the pulses in ns. Must be above 16ns and a multiple of 4ns.
        digital_marker (str, optional): The digital marker for the pulses. Defaults to None. Can be set to "ON".
    """
    if nv_center.xy is not None:
        nv_center.xy.operations["x180_Square"] = pulses.SquarePulse(
            length=length,
            amplitude=amplitude,
            digital_marker=digital_marker,
            axis_angle=0,
        )
        nv_center.xy.operations["x90_Square"] = pulses.SquarePulse(
            length="#../x180_Square/length",
            amplitude=amplitude / 2,
            digital_marker="#../x180_Square/digital_marker",
            axis_angle=0,
        )
        nv_center.xy.operations["-x90_Square"] = pulses.SquarePulse(
            length="#../x180_Square/length",
            amplitude="#../x90_Square/amplitude",
            digital_marker="#../x180_Square/digital_marker",
            axis_angle=np.pi,
        )
        nv_center.xy.operations["y180_Square"] = pulses.SquarePulse(
            length="#../x180_Square/length",
            amplitude="#../x180_Square/amplitude",
            digital_marker="#../x180_Square/digital_marker",
            axis_angle=np.pi / 2,
        )
        nv_center.xy.operations["y90_Square"] = pulses.SquarePulse(
            length="#../x180_Square/length",
            amplitude="#../x90_Square/amplitude",
            digital_marker="#../x180_Square/digital_marker",
            axis_angle=np.pi / 2,
        )
        nv_center.xy.operations["-y90_Square"] = pulses.SquarePulse(
            length="#../x180_Square/length",
            amplitude="#../x90_Square/amplitude",
            digital_marker="#../x180_Square/digital_marker",
            axis_angle=-np.pi / 2,
        )
        nv_center.set_gate_shape("Square")


def add_default_nv_center_pulses(
    nv_center: NVCenter
):
    """Adds default pulses to a nv_center qubit:
        * nv_center.xy.operations["cw"] = pulses.SquarePulse(amplitude=0.25, length=20 * u.us, axis_angle=0)
        * nv_center.laser.operations["laser_on"] = pulses.SquarePulse(length=2000, amplitude=0.0, digital_marker="ON")
        * nv_center.spcm.operations["readout"] = pulses.ReadoutPulse(length=400, digital_marker="ON")

    Args:
        nv_center (NVCenter): The nv_center qubit to which the pulses will be added.
    """
    if hasattr(nv_center, "xy"):
        if nv_center.xy is not None:
            nv_center.xy.operations["cw"] = pulses.SquarePulse(
                amplitude=0.25, length=20 * u.us, axis_angle=0
            )

    if hasattr(nv_center, "laser"):
        if nv_center.laser.trigger is not None:
            nv_center.laser.trigger.operations["laser_on"] = pulses.Pulse(
                length=3000 * u.ns, digital_marker="ON"
            )
            nv_center.laser.trigger.operations["laser_off"] = pulses.Pulse(
                length="#../laser_on/length", digital_marker=[[0, 0]]
            )

    if hasattr(nv_center, "spcm"):
        if nv_center.spcm is not None:
            nv_center.spcm.operations["readout"] = pulses.ReadoutPulse(
                length=500 * u.ns, digital_marker=None
            )


def add_default_nv_center_pair_pulses(
    nv_center_pair: NVCenterPair
):
    """Adds default pulses to a nv_center qubit pair depending on its attributes:
        * nv_center_pair.coupler.operations["const"] = pulses.SquarePulse(amplitude=0.1, length=100)
        * nv_center_pair.cross_resonance.operations["square"] = pulses.SquarePulse(amplitude=0.1, length=100)
        * nv_center_pair.zz_drive.operations["square"] = pulses.SquarePulse(amplitude=0.1, length=100)

    Args:
        nv_center_pair (NVCenterPair): The nv_center qubit pair to which the pulses will be added.
    """
    pass
