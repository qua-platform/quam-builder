from typing import Optional

from quam.core import QuamComponent, quam_dataclass
from quam.components.channels import Channel, SingleChannel


__all__ = ["LaserControl", "LaserLFAnalog", "LaserLFDigital"]


@quam_dataclass
class LaserLFAnalog(SingleChannel):
    """
    QUAM component for a laser to set the laser power.

    Attributes:
        dc_voltage (float): the voltage setpoints to control the laser power in V.
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

    Attributes:
        trigger Optional[LaserLFDigital]: the digital laser trigger component.
        power Optional[LaserLFAnalog]: the laser power control component.
    """

    trigger: Optional[LaserLFDigital] = None
    power: Optional[LaserLFAnalog] = None

    @property
    def name(self) -> str:
        """Returns the name of the laser component"""
        return f"{self.parent.id}.laser"
