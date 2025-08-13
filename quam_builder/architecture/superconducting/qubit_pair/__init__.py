from typing import Union
from quam_builder.architecture.superconducting.qubit_pair.flux_tunable_transmon_pair import (
    FluxTunableTransmonPair,
    FluxTunableCrossDriveTransmonPair,
)
from quam_builder.architecture.superconducting.qubit_pair.fixed_frequency_transmon_pair import (
    FixedFrequencyTransmonPair,
)

__all__ = [
    *fixed_frequency_transmon_pair.__all__,
    *flux_tunable_transmon_pair.__all__,
]

AnyTransmonPair = Union[FixedFrequencyTransmonPair, FluxTunableTransmonPair, FluxTunableCrossDriveTransmonPair]
