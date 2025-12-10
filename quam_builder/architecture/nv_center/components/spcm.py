from quam.components.channels import InOutSingleChannel
from quam.core import quam_dataclass

__all__ = ["SPCM"]


@quam_dataclass
class SPCM(InOutSingleChannel):
    """
    QUAM component for a readout.
    """

    pass
