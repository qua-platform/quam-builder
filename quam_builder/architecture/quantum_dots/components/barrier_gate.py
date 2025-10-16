

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.components import VoltageGate


__all__ = ["BarrierGate"]


@quam_dataclass
class BarrierGate(VoltageGate):
    """
    A class for a BarrierGate channel
    """

    pass
