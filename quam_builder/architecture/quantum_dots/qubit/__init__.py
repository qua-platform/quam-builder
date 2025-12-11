from typing import Union

from . import ld_qubit
from .ld_qubit import *

__all__ = [ld_qubit.__all__]

AnySpinQubit = Union[LDQubit]
