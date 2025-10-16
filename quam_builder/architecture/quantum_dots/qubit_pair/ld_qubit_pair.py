from quam.core import quam_dataclass
from quam.components import QubitPair

from quam_builder.architecture.quantum_dots.components import QuantumDotPair

__all__ = ["LDQubitPair"]


@quam_dataclass
class LDQubitPair(QubitPair):
    """
    A class representing a pair of LD qubits.
    """
    qd_pair: QuantumDotPair

    pass


