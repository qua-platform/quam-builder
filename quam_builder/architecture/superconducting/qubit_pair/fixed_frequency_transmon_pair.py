from typing import Dict, Any, Optional, Union
from dataclasses import field
from qm.qua import align, wait

from quam.core import quam_dataclass
from quam.components.quantum_components import QuantumComponent
from quam.components.channels import IQChannel, MWChannel
from quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon import (
    FixedFrequencyTransmon,
)
from quam_builder.architecture.superconducting.components.cross_resonance import (
    CrossResonanceIQ,
    CrossResonanceMW,
)
from quam_builder.architecture.superconducting.components.zz_drive import (
    ZZDriveIQ,
    ZZDriveMW,
)


__all__ = ["FixedFrequencyTransmonPair"]


@quam_dataclass
class FixedFrequencyTransmonPair(QuantumComponent):
    id: Union[int, str]

    cross_resonance: Optional[Union[CrossResonanceMW, CrossResonanceIQ]] = None
    zz_drive: Optional[Union[ZZDriveMW, ZZDriveIQ]] = None
    xy_detuned: Union[MWChannel, IQChannel] = None
    confusion: list = None

    extras: Dict[str, Any] = field(default_factory=dict)
