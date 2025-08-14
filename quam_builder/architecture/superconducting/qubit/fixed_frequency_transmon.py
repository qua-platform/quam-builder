from typing import Union
from quam.core import quam_dataclass

from quam.components.channels import IQChannel, MWChannel
from quam_builder.architecture.superconducting.qubit.base_transmon import BaseTransmon

__all__ = ["FixedFrequencyTransmon",  "FixedFrequencyZZDriveTransmon"]


@quam_dataclass
class FixedFrequencyTransmon(BaseTransmon):
    """
    Example QUAM component for a transmon qubit.

    Args:

    """

    pass


@quam_dataclass
class FixedFrequencyZZDriveTransmon(FixedFrequencyTransmon):
    """Quam Component for flux-tunable features and added Stark ZZ drive."""
    
    xy_detuned: Union[MWChannel, IQChannel] = None
