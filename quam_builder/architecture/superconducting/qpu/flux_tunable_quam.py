import warnings
from dataclasses import field
from typing import Dict, Union, ClassVar, Type

from quam.core import quam_dataclass

from quam_builder.architecture.superconducting.qubit import FluxTunableTransmon
from quam_builder.architecture.superconducting.qubit_pair import FluxTunableTransmonPair, FluxTunableCrossDriveTransmonPair
from quam_builder.architecture.superconducting.qpu.base_quam import BaseQuam


__all__ = ["FluxTunableQuam", "FluxTunableCrossDriveQuam", "FluxTunableTransmon", "FluxTunableTransmonPair"]


@quam_dataclass
class FluxTunableQuam(BaseQuam):
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

    qubit_type: ClassVar[Type[FluxTunableTransmon]] = FluxTunableTransmon
    qubit_pair_type: ClassVar[Type[FluxTunableTransmonPair]] = FluxTunableTransmonPair

    qubits: Dict[str, FluxTunableTransmon] = field(default_factory=dict)
    qubit_pairs: Dict[str, FluxTunableTransmonPair] = field(default_factory=dict)

    @classmethod
    def load(cls, *args, **kwargs) -> "FluxTunableQuam":
        return super().load(*args, **kwargs)

    def apply_all_couplers_to_min(self) -> None:
        """Apply the offsets that bring all the active qubit pairs to a decoupled point."""
        for qp in self.active_qubit_pairs:
            if qp.coupler is not None:
                qp.coupler.to_decouple_idle()

    def apply_all_flux_to_joint_idle(self) -> None:
        """Apply the offsets that bring all the active qubits to the joint sweet spot."""
        for q in self.active_qubits:
            if q.z is not None:
                q.z.to_joint_idle()
            else:
                warnings.warn(
                    f"Didn't find z-element on qubit {q.name}, didn't set to joint-idle"
                )
        for q in self.qubits:
            if self.qubits[q] not in self.active_qubits:
                if self.qubits[q].z is not None:
                    self.qubits[q].z.to_min()
                else:
                    warnings.warn(
                        f"Didn't find z-element on qubit {q}, didn't set to min"
                    )
        self.apply_all_couplers_to_min()

    def apply_all_flux_to_min(self) -> None:
        """Apply the offsets that bring all the active qubits to the minimum frequency point."""
        for q in self.qubits:
            if self.qubits[q].z is not None:
                self.qubits[q].z.to_min()
            else:
                warnings.warn(f"Didn't find z-element on qubit {q}, didn't set to min")
        self.apply_all_couplers_to_min()

    def apply_all_flux_to_zero(self) -> None:
        """Apply the offsets that bring all the active qubits to the zero bias point."""
        for q in self.active_qubits:
            q.z.to_zero()

    def set_all_fluxes(
        self,
        flux_point: str,
        target: Union[FluxTunableTransmon, FluxTunableTransmonPair],
    ):
        """Set the fluxes to the specified point for the target qubit or qubit pair.

        Args:
            flux_point (str): The flux point to set ('independent', 'pairwise', 'joint', 'min').
            target (Union[FluxTunableTransmon, FluxTunableTransmonPair]): The target qubit or qubit pair.
        """
        if flux_point == "independent":
            assert isinstance(
                target, FluxTunableTransmon
            ), "Independent flux point is only supported for individual transmons"
        elif flux_point == "pairwise":
            assert isinstance(
                target, FluxTunableTransmonPair
            ), "Pairwise flux point is only supported for transmon pairs"

        target_bias = None
        if flux_point == "joint":
            self.apply_all_flux_to_joint_idle()
            if isinstance(target, FluxTunableTransmonPair):
                target_bias = target.mutual_flux_bias
            else:
                target_bias = target.z.joint_offset
        else:
            self.apply_all_flux_to_min()

        if flux_point == "independent":
            target.z.to_independent_idle()
            target_bias = target.z.independent_offset

        elif flux_point == "pairwise":
            target.to_mutual_idle()
            target_bias = target.mutual_flux_bias

        target.z.settle()
        target.align()
        return target_bias

    def initialize_qpu(self, **kwargs):
        """Initialize the QPU with the specified flux point and target.

        Args:
            flux_point (str): The flux point to set. Default is 'joint'.
            target: The qubit under study.
        """
        flux_point = kwargs.get("flux_point", "joint")
        target = kwargs.get("target", None)
        self.set_all_fluxes(flux_point, target)


class FluxTunableCrossDriveQuam(FluxTunableQuam):
    """Example of a QUAM composed of flux tunable cr transmons.

    Attributes:
        qubit_pair_type (ClassVar[Type[FixedFrequencyTransmonPair]]): The type of the qubit pairs in the QUAM for type hinting.
        qubit_pairs (Dict[str, FixedFrequencyTransmonPair]): A dictionary of qubit pairs composing the QUAM.

    """
    qubit_pair_type: ClassVar[Type[FluxTunableCrossDriveTransmonPair]] = FluxTunableCrossDriveTransmonPair
    qubit_pairs: Dict[str, FluxTunableCrossDriveTransmonPair] = field(default_factory=dict)

    @classmethod
    def load(cls, *args, **kwargs) -> "FluxTunableCrossDriveQuam":
        return super().load(*args, **kwargs)
    