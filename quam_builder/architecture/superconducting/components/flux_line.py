from typing import Literal

from quam.core import quam_dataclass
from quam.components import SingleChannel


__all__ = ["FluxLine"]


@quam_dataclass
class FluxLine(SingleChannel):
    """QUAM component for a flux line.

    Attributes:
        independent_offset (float): the flux bias corresponding to the resonator maximum frequency when all the active
            qubits are not interacting (min offset) in V.
        joint_offset (float): the flux bias corresponding to the resonator maximum frequency when all the active qubits
            are at their sweet spot (joint offset) in V.
        min_offset (float): the flux bias corresponding to the resonator minimum frequency when all the active qubits
            are not interacting (min offset) in V.
        arbitrary_offset (float): arbitrary flux bias in V.
        flux_point (str): name of the flux point to set the qubit at. Can be among ["joint", "independent", "min",
            "arbitrary", "zero"]. Default is "independent".
        settle_time (float): the flux line settle time in ns. The value will be cast to an integer multiple of 4ns
            automatically.
    """

    independent_offset: float = 0.0
    joint_offset: float = 0.0
    min_offset: float = 0.0
    arbitrary_offset: float = 0.0
    flux_point: Literal["joint", "independent", "min", "arbitrary", "zero"] = (
        "independent"
    )
    settle_time: float = None

    def settle(self):
        """Wait for the flux bias to settle"""
        if self.settle_time is not None:
            self.wait(int(self.settle_time) // 4 * 4)

    def to_independent_idle(self):
        """Set the flux bias to the independent offset: qubit at the sweet spot while all the others are at the minimum frequency point."""
        self.set_dc_offset(self.independent_offset)

    def to_joint_idle(self):
        """Set the flux bias to the joint offset: qubit at the sweet spot while all the others are at the sweep spot."""
        self.set_dc_offset(self.joint_offset)

    def to_min(self):
        """Set the flux bias to the min offset: qubit at the minimum frequency point while all the others are at the minimum frequency point."""
        self.set_dc_offset(self.min_offset)

    def to_zero(self):
        """Set the flux bias to 0.0 V"""
        self.set_dc_offset(0.0)
