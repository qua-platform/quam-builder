from quam.core import quam_dataclass
from quam.components.channels import InOutSingleChannel


__all__ = ["SPCM"]


@quam_dataclass
class SPCM(InOutSingleChannel):
    """
    QUAM component for a readout.
    """

    readout_time: int = 400
