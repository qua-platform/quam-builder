from quam.core import quam_dataclass
from quam.components.channels import InSingleChannel


__all__ = ["SPCM"]


@quam_dataclass
class SPCM(InSingleChannel):
    """
    QUAM component for a readout.
    """

    pass
