from . import base_quam_qd
from .base_quam_qd import *
from . import loss_divincenzo_quam
from .loss_divincenzo_quam import *
from . import exchange_only_quam
from .exchange_only_quam import *
from . import base_qubit_quam
from .base_qubit_quam import *
from typing import Union

__all__ = [
    *base_quam_qd.__all__,
    *base_qubit_quam.__all__,
    *loss_divincenzo_quam.__all__,
    *exchange_only_quam.__all__,
]

AnyQuamQD = Union[BaseQuamQD, BaseSpinQubitQuam, LossDiVincenzoQuam, ExchangeOnlyQuam]
