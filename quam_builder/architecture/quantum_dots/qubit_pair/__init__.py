from typing import Union

from . import ld_qubit_pair
from .ld_qubit_pair import *
from .exchange_only_qubit_pair import *

__all__ = [
    *ld_qubit_pair.__all__,
    *ExchangeOnlyQubitPair.__all__,
]

AnySpinQubitPair = Union[LDQubitPair, ExchangeOnlyQubitPair]
