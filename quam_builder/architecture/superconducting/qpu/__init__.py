from typing import Union

from . import base_quam, fixed_frequency_quam, flux_tunable_quam
from .base_quam import *
from .fixed_frequency_quam import *
from .flux_tunable_quam import *

__all__ = [
    *base_quam.__all__,
    *fixed_frequency_quam.__all__,
    *flux_tunable_quam.__all__,
]

AnyQuam = Union[BaseQuam, FixedFrequencyQuam, FluxTunableQuam]
