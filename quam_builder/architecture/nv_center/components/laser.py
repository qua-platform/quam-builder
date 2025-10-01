from typing import Optional

from quam.core import quam_dataclass
from quam.components.channels import Channel, SingleChannel


__all__ = ["LaserLFAnalog", "LaserLFDigital"]


@quam_dataclass
class LaserLFAnalog(SingleChannel):
    """
    QUAM component for a laser.

    Attributes:
        laser_length (int): The laser pulse time in ns. Default is 1000ns.
    """

    pass


@quam_dataclass
class LaserLFDigital(Channel):
    """
    QUAM component for a laser.

    Attributes:
        laser_length (int): The laser pulse time in ns. Default is 1000ns.
    """

    pass
