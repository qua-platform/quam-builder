from typing import Optional

from quam.core import quam_dataclass
from quam.components.channels import Channel, SingleChannel


__all__ = ["LaserLFAnalog", "LaserLFDigital"]


@quam_dataclass
class LaserLFAnalog(SingleChannel):
    """
    QUAM component for a laser.
    """

    pass


@quam_dataclass
class LaserLFDigital(Channel):
    """
    QUAM component for a laser.
    """

    pass
