from typing import Union

from quam_builder.architecture.superconducting.qpu.base_quam import BaseQuam
from quam_builder.architecture.superconducting.qpu.fixed_frequency_quam import (
    FixedFrequencyQuam,
    ParametricQuam,
)
from quam_builder.architecture.superconducting.qpu.flux_tunable_quam import (
    FluxTunableQuam,
)

__all__ = [
    *base_quam.__all__,
    *fixed_frequency_quam.__all__,
    *flux_tunable_quam.__all__,
]

AnyQuam = Union[BaseQuam, FixedFrequencyQuam, FluxTunableQuam, ParametricQuam]
