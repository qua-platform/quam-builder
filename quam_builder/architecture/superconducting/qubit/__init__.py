from typing import Union

from . import base_transmon, fixed_frequency_transmon, flux_tunable_transmon
from .base_transmon import *
from .fixed_frequency_transmon import *
from .flux_tunable_transmon import *

__all__ = [
    *base_transmon.__all__,
    *fixed_frequency_transmon.__all__,
    *flux_tunable_transmon.__all__,
]

AnyTransmon = Union[BaseTransmon, FixedFrequencyTransmon, FluxTunableTransmon]
