from quam.core import quam_dataclass
from quam_builder.architecture.superconducting.qubit.base_transmon import BaseTransmon

__all__ = ["FixedFrequencyTransmon"]


# todo: shall this on be the base Transmon directly?
@quam_dataclass
class FixedFrequencyTransmon(BaseTransmon):
    """
    Example QUAM component for a transmon qubit.

    Args:

    """

    pass
