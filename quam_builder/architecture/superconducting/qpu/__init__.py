from quam_builder.architecture.superconducting.qpu.base_quam import BaseQuam
from quam_builder.architecture.superconducting.qpu.fixed_frequency_quam import (
    FixedFrequencyQuam,
)
from quam_builder.architecture.superconducting.qpu.flux_tunable_quam import (
    FluxTunableQuam, FluxTunableQuamReset
)
from typing import Union

__all__ = [
    *base_quam.__all__,
    *fixed_frequency_quam.__all__,
    *flux_tunable_quam.__all__,
]

AnyQuam = Union[BaseQuam, FixedFrequencyQuam, FluxTunableQuam, FluxTunableQuamReset]
