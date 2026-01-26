

from quam.core import quam_dataclass
from quam.components.channels import InSingleChannel, InMWChannel, InIQChannel


__all__ = ["ReadoutTransportBase", "ReadoutTransportSingle"]

@quam_dataclass
class ReadoutTransportBase:
    """
    Quam component for a transport measurement. 
    """
    pass

@quam_dataclass
class ReadoutTransportSingle(InSingleChannel, ReadoutTransportBase): 
    """
    A Quam component for a transport measurement setup using the LF-FEM. 
    """
    pass
