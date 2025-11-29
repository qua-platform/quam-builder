from typing import Union

from . import fixed_frequency_transmon_pair, flux_tunable_transmon_pair
from .fixed_frequency_transmon_pair import *
from .flux_tunable_transmon_pair import *

__all__ = [
    *fixed_frequency_transmon_pair.__all__,
    *flux_tunable_transmon_pair.__all__,
]

AnyTransmonPair = Union[FixedFrequencyTransmonPair, FluxTunableTransmonPair]
