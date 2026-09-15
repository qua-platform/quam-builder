from typing import Union

from . import ld_qubit_pair
from .ld_qubit_pair import *
from .singlet_triplet_qubit_pair import *

__all__ = [
    *ld_qubit_pair.__all__,
    *singlet_triplet_qubit_pair.__all__,
]

AnySpinQubitPair = Union[LDQubitPair, SingletTripletQubitPair]
