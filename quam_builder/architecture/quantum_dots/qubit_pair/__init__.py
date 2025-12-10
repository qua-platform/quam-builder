from . import ld_qubit_pair
from .ld_qubit_pair import LDQubitPair

__all__ = [
    *ld_qubit_pair.__all__,
]

AnySpinQubitPair = LDQubitPair
