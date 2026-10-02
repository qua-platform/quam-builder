from typing import Union

from . import ld_qubit
from .ld_qubit import *
from .eo_qubit import *

from typing import Union

AnySpinQubit = Union[LDQubit, ExchangeOnlyQubit]

__all__ = ["LDQubit", "ExchangeOnlyQubit", "AnySpinQubit"]
