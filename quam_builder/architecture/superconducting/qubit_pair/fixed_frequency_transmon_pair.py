from dataclasses import field
from typing import Any, Dict, Optional, Union

from quam_builder.architecture.superconducting.components.cross_resonance import (
    CrossResonanceIQ,
    CrossResonanceMW,
)
from quam_builder.architecture.superconducting.components.tunable_coupler import (
    TunableCoupler,
)
from quam_builder.architecture.superconducting.components.zz_drive import (
    ZZDriveIQ,
    ZZDriveMW,
)
from quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon import (
    FixedFrequencyTransmon,
)

from quam.components.channels import IQChannel, MWChannel
from quam.components.quantum_components import QubitPair
from quam.core import quam_dataclass
from qm.qua import align


__all__ = ["FixedFrequencyTransmonPair", "ParametricTransmonPair"]


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

    id: Union[int, str]
    qubit_control: FixedFrequencyTransmon = None
    qubit_target: FixedFrequencyTransmon = None

    cross_resonance: Optional[Union[CrossResonanceMW, CrossResonanceIQ]] = None
    zz_drive: Optional[Union[ZZDriveMW, ZZDriveIQ]] = None
    xy_detuned: Union[MWChannel, IQChannel] = None

    confusion: list = None

    extras: Dict[str, Any] = field(default_factory=dict)


@quam_dataclass
class ParametricTransmonPair(QubitPair):
    """
    Example QUAM component for a fixed-frequency transmon qubit pair with a parametric tunable coupler.

    This component represents a pair of fixed-frequency transmon qubits connected via a tunable coupler that enables parametric interactions.

    Attributes:
        id (Union[int, str]): The id of the Transmon pair, used to generate the name.
            Can be a string, or an integer in which case it will add `Channel._default_label`.
        qubit_control (FixedFrequencyTransmon): The control qubit of the pair.
        qubit_target (FixedFrequencyTransmon): The target qubit of the pair.
        coupler (TunableCoupler): The tunable coupler component connecting the two qubits for parametric interactions.
        confusion (list): The readout confusion matrix.
        extras (Dict[str, Any]): Additional attributes for the transmon pair.
    """

    id: Union[int, str]
    qubit_control: FixedFrequencyTransmon = None
    qubit_target: FixedFrequencyTransmon = None

    coupler: TunableCoupler = None

    confusion: list = None

    extras: Dict[str, Any] = field(default_factory=dict)

    def align(self):
        """Aligns the channels of the control and target qubits, and the coupler if present."""
        channels = []
        for qubit in [self.qubit_control, self.qubit_target]:
            channels += [ch.name for ch in qubit.channels.values()]

        if self.coupler:
            channels += [self.coupler.name]

        align(*channels)
