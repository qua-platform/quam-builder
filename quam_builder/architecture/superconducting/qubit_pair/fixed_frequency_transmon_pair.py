from typing import Dict, Any, Optional, Union
from dataclasses import field

from quam.core import quam_dataclass
from quam.components.channels import IQChannel, MWChannel
from quam.components.quantum_components import QubitPair
from quam_builder.architecture.superconducting.components.cross_resonance import (
    CrossResonanceIQ,
    CrossResonanceMW,
)
from quam_builder.architecture.superconducting.components.zz_drive import (
    ZZDriveIQ,
    ZZDriveMW,
)
from quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon import FixedFrequencyTransmon


__all__ = ["FixedFrequencyTransmonPair"]


@quam_dataclass
class FixedFrequencyTransmonPair(QubitPair):
    id: Union[int, str]
    qubit_control: FixedFrequencyTransmon = None
    qubit_target: FixedFrequencyTransmon = None

    cross_resonance: Optional[Union[CrossResonanceMW, CrossResonanceIQ]] = None
    zz_drive: Optional[Union[ZZDriveMW, ZZDriveIQ]] = None
    xy_detuned: Union[MWChannel, IQChannel] = None

    confusion: list = None

    extras: Dict[str, Any] = field(default_factory=dict)
