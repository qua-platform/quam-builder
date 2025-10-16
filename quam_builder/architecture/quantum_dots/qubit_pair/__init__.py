from typing import Union
from .ld_qubit_pair import *

__all__ = [
    *ld_qubit_pair.__all__,
]

AnySpinQubitPair = Union[LDQubitPair]