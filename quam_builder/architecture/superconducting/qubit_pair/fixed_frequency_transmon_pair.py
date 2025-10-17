from typing import Dict, Any, Optional, Union
from dataclasses import field
from quam.components import SingleChannel
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
        parametric_drive (Optional[SingleChannel]): The primary parametric drive channel.
        parametric_drive_alt (Optional[SingleChannel]): An alternative parametric drive channel, 
        for pairs with multiple clusters available.
        confusion (list): The readout confusion matrix.
        extras (Dict[str, Any]): Additional attributes for the transmon pair.
    """

    id: Union[int, str]
    qubit_control: FixedFrequencyTransmon = None
    qubit_target: FixedFrequencyTransmon = None

    cross_resonance: Optional[Union[CrossResonanceMW, CrossResonanceIQ]] = None
    zz_drive: Optional[Union[ZZDriveMW, ZZDriveIQ]] = None
    xy_detuned: Union[MWChannel, IQChannel] = None
    parametric_drive: Optional[SingleChannel] = None
    parametric_drive_alt: Optional[SingleChannel] = None

    confusion: list = None

    extras: Dict[str, Any] = field(default_factory=dict)
