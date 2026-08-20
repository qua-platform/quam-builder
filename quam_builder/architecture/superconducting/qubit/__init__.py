from quam_builder.architecture.superconducting.qubit.base_transmon import BaseTransmon
from quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon import (
    FixedFrequencyTransmon,
    FixedFrequencyZZDriveTransmon,
)
from quam_builder.architecture.superconducting.qubit.flux_tunable_transmon import (
    FluxTunableTransmon,
)
from typing import Union

__all__ = [
    *base_transmon.__all__,
    *fixed_frequency_transmon.__all__,
    *flux_tunable_transmon.__all__,
]

AnyTransmon = Union[
    BaseTransmon,
    FixedFrequencyTransmon,
    FixedFrequencyZZDriveTransmon,
    FluxTunableTransmon,
]

AnyFixedFrequencyTransmon = Union[
    FixedFrequencyTransmon,
    FixedFrequencyZZDriveTransmon,
]