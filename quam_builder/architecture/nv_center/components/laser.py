from typing import Optional

from quam.core import QuamComponent, quam_dataclass
from quam.components.channels import Channel, SingleChannel


__all__ = ["LaserLFAnalog", "LaserLFDigital"]


@quam_dataclass
class LaserLFAnalog(SingleChannel):
    """
    QUAM component for a laser to set the laser power.
    """

    dc_voltage: float = 1.0  # power control in volts


@quam_dataclass
class LaserLFDigital(Channel):
    """
    QUAM component for a laser.
    """

    pass


@quam_dataclass
class LaserControl(QuamComponent):
    """
    QUAM component of the laser.
    Includes a digital laser trigger and analog control for the laser power.
    """

    trigger: Optional[LaserLFDigital] = None
    power: Optional[LaserLFAnalog] = None
