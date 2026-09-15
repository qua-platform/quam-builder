from typing import Union

from .ld_qubit import *
from .singlet_triplet_qubit import *

from typing import Union

AnySpinQubit = Union[LDQubit, SingletTripletQubit]

__all__ = ["LDQubit", "AnySpinQubit", "SingletTripletQubit"]
