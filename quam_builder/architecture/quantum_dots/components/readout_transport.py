"""Transport readout channel components."""

from quam.core import quam_dataclass
from quam.components.channels import InSingleChannel, InOutSingleChannel, InMWChannel, InIQChannel


__all__ = ["ReadoutTransportBase", "ReadoutTransportSingle", "ReadoutTransportSingleIO"]


@quam_dataclass
class ReadoutTransportBase:  # pylint: disable=too-few-public-methods
    """
    Quam component for a transport measurement.
    """

    pass


@quam_dataclass
class ReadoutTransportSingle(
    InSingleChannel, ReadoutTransportBase
):  # pylint: disable=too-few-public-methods
    """
    A Quam component for a transport measurement setup using the LF-FEM.
    """

    pass


@quam_dataclass
class ReadoutTransportSingleIO(
    InOutSingleChannel, ReadoutTransportBase
):  # pylint: disable=too-few-public-methods
    """
    A transport measurement channel with both input and output.

    This is useful when a measurement pulse is required for configuration, even if
    the output amplitude is set to zero in practice.
    """

    pass
