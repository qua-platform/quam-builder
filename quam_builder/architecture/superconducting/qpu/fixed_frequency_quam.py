from dataclasses import field
from typing import ClassVar, Dict, Type

from quam_builder.architecture.superconducting.qpu.base_quam import BaseQuam
from quam_builder.architecture.superconducting.qubit import FixedFrequencyTransmon
from quam_builder.architecture.superconducting.qubit_pair import (
    FixedFrequencyTransmonPair,
    FluxTunableTransmonPair,
    ParametricTransmonPair,
)

from quam.core import quam_dataclass

__all__ = [
    "FixedFrequencyQuam",
    "FixedFrequencyTransmon",
    "FixedFrequencyTransmonPair",
    "ParametricQuam",
]


@quam_dataclass
class FixedFrequencyQuam(BaseQuam):
    """Example of a QUAM composed of fixed frequency transmons.

    Attributes:
        qubit_type (ClassVar[Type[FixedFrequencyTransmon]]): The type of the qubits in the QUAM for type hinting.
        qubit_pair_type (ClassVar[Type[FixedFrequencyTransmonPair]]): The type of the qubit pairs in the QUAM for type hinting.
        qubits (Dict[str, FixedFrequencyTransmon]): A dictionary of qubits composing the QUAM.
        qubit_pairs (Dict[str, FixedFrequencyTransmonPair]): A dictionary of qubit pairs composing the QUAM.

    Methods:
        load: Loads the QUAM from the state.json file.
    """

    qubit_type: ClassVar[Type[FixedFrequencyTransmon]] = FixedFrequencyTransmon
    qubit_pair_type: ClassVar[Type[FixedFrequencyTransmonPair]] = (
        FixedFrequencyTransmonPair
    )

    qubits: Dict[str, FixedFrequencyTransmon] = field(default_factory=dict)
    qubit_pairs: Dict[str, FixedFrequencyTransmonPair] = field(default_factory=dict)

    @classmethod
    def load(cls, *args, **kwargs) -> "FixedFrequencyQuam":
        return super().load(*args, **kwargs)


@quam_dataclass
class ParametricQuam(BaseQuam):
    """Example of a QUAM composed of flux tunable transmons.

    Attributes:
        qubit_type (ClassVar[Type[FixedFrequencyTransmon]]): The type of the qubits in the QUAM for type hinting.
        qubit_pair_type (ClassVar[Type[FixedFrequencyTransmonPair]]): The type of the qubit pairs in the QUAM for type hinting.
        qubits (Dict[str, FixedFrequencyTransmon]): A dictionary of qubits composing the QUAM.
        qubit_pairs (Dict[str, FixedFrequencyTransmonPair]): A dictionary of qubit pairs composing the QUAM.

    Methods:
        load: Loads the QUAM from the state.json file.
        apply_all_couplers_to_min: Apply the offsets that bring all the active qubit pairs to a decoupled point.
        apply_all_flux_to_joint_idle: Apply the offsets that bring all the active qubits to the joint sweet spot.
        apply_all_flux_to_min: Apply the offsets that bring all the active qubits to the minimum frequency point.
        apply_all_flux_to_zero: Apply the offsets that bring all the active qubits to the zero bias point.
        set_all_fluxes: Set the fluxes to the specified point for the target qubit or qubit pair.
        initialize_qpu: Initialize the QPU with the specified flux point and target.
    """

    qubit_type: ClassVar[Type[FixedFrequencyTransmon]] = FixedFrequencyTransmon
    qubit_pair_type: ClassVar[Type[ParametricTransmonPair]] = ParametricTransmonPair

    qubits: Dict[str, FixedFrequencyTransmon] = field(default_factory=dict)
    qubit_pairs: Dict[str, ParametricTransmonPair] = field(default_factory=dict)

    @classmethod
    def load(cls, *args, **kwargs) -> "ParametricQuam":
        return super().load(*args, **kwargs)

    def apply_all_couplers_to_min(self) -> None:
        """Apply the offsets that bring all the active qubit pairs to a decoupled point."""
        for qp in self.active_qubit_pairs:
            if qp.coupler is not None:
                qp.coupler.to_decouple_idle()

    def initialize_qpu(self, **kwargs):
        """Initialize the QPU with the specified flux point and target.

        Args:
            flux_point (str): The flux point to set. Default is 'joint'.
            target: The qubit under study.
        """
        self.apply_all_couplers_to_min()
