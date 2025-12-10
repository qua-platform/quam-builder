from dataclasses import field
from typing import Any

from quam.components.channels import IQChannel, MWChannel
from quam.components.quantum_components import QubitPair
from quam.core import quam_dataclass
from quam_builder.architecture.superconducting.components.cross_resonance import (
    CrossResonanceIQ,
    CrossResonanceMW,
)
from quam_builder.architecture.superconducting.components.zz_drive import (
    ZZDriveIQ,
    ZZDriveMW,
)
from quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon import (
    FixedFrequencyTransmon,
)

__all__ = ["FixedFrequencyTransmonPair"]


@quam_dataclass
class FixedFrequencyTransmonPair(QubitPair):
    """Example QUAM component for a fixed-frequency transmon qubit pair.

    Attributes:
        id (Union[int, str]): The id of the Transmon pair, used to generate the name.
            Can be a string, or an integer in which case it will add `Channel._default_label`.
        qubit_control (FixedFrequencyTransmon): The control qubit of the pair.
        qubit_target (FixedFrequencyTransmon): The target qubit of the pair.
        cross_resonance (Optional[Union[CrossResonanceMW, CrossResonanceIQ]]): The cross resonance component.
        zz_drive (Optional[Union[ZZDriveMW, ZZDriveIQ]]): The ZZ drive component.
        xy_detuned (Union[MWChannel, IQChannel]): The detuned xy drive component.
        confusion (list): The readout confusion matrix.
        extras (Dict[str, Any]): Additional attributes for the transmon pair.
    """

    id: int | str
    qubit_control: FixedFrequencyTransmon = None
    qubit_target: FixedFrequencyTransmon = None

    cross_resonance: CrossResonanceMW | CrossResonanceIQ | None = None
    zz_drive: ZZDriveMW | ZZDriveIQ | None = None
    xy_detuned: MWChannel | IQChannel = None

    confusion: list = None

    extras: dict[str, Any] = field(default_factory=dict)
