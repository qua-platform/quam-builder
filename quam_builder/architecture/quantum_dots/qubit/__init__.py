from typing import Union

from . import ld_qubit
from .ld_qubit import *

AnySpinQubit = Union[LDQubit]

__all__ = ["LDQubit", "AnySpinQubit"]
