from typing import Dict, List

from quam.core import quam_dataclass, QuamComponent
from quam.components import InSingleChannel

from .mixins import VoltageMacroMixin
from .quantum_dot import QuantumDot
from .voltage_gate import VoltageGate
from .readout_transport import ReadoutTransportBase

__all__ = ["ReservoirBase", "DrainSingle"]


@quam_dataclass
class ReservoirBase(VoltageGate):  # pylint: disable=too-many-ancestors
    """
    Base class for a reservoir in a quantum dot device.
    """

    id: str = None

    @property
    def machine(self) -> "BaseQuamQD":
        # Climb up the parent ladder in order to find the VoltageSequence in the machine
        obj = self
        while obj.parent is not None:
            obj = obj.parent
        machine = obj
        return machine

    @property
    def name(self) -> str:
        return self.id


@quam_dataclass
class DrainSingle(ReservoirBase):  # pylint: disable=too-many-ancestors
    """
    Quam component for the drain ohmic contact of a QD Device.
    """

    readout: ReadoutTransportBase = None


@quam_dataclass
class SourceSingle(ReservoirBase):  # pylint: disable=too-many-ancestors
    """
    Quam component for the source ohmic contact of a QD Device. Include in the virtual channel mapping
    if virtualization is required.
    """

    pass
