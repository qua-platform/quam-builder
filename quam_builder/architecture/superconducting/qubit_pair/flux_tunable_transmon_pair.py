from dataclasses import field
from typing import Any

from qm.qua import align, wait
from quam.components.quantum_components import QubitPair
from quam.core import quam_dataclass
from quam_builder.architecture.superconducting.components.tunable_coupler import (
    TunableCoupler,
)
from quam_builder.architecture.superconducting.qubit.flux_tunable_transmon import (
    FluxTunableTransmon,
)

__all__ = ["FluxTunableTransmonPair"]


@quam_dataclass
class FluxTunableTransmonPair(QubitPair):
    """Example QUAM component for a flux-tunable transmon qubit pair.

    Attributes:
        id (Union[int, str]): The id of the Transmon pair, used to generate the name.
            Can be a string, or an integer in which case it will add `Channel._default_label`.
        qubit_control (FluxTunableTransmon): The control qubit of the pair.
        qubit_target (FluxTunableTransmon): The target qubit of the pair.
        coupler (Optional[TunableCoupler]): The tunable coupler component.
        detuning (Optional[float]): Flux amplitude required to bring the qubits to the same energy in V
        confusion (list): The readout confusion matrix.
        mutual_flux_bias (List[float]): The mutual flux bias values for the control and target qubits. Default is [0, 0].
        extras (Dict[str, Any]): Additional attributes for the transmon pair.

    Methods:
        align: Aligns the channels of the control and target qubits, and the coupler if present.
        wait: Waits for the specified duration on the channels of the control and target qubits, and the coupler if present.
        to_mutual_idle: Sets the flux bias to the mutual idle offset for the control and target qubits.
    """

    id: int | str
    qubit_control: FluxTunableTransmon = None
    qubit_target: FluxTunableTransmon = None
    coupler: TunableCoupler | None = None

    detuning: float | None = None
    confusion: list[list[float]] | None = None
    mutual_flux_bias: list[float] = field(default_factory=lambda: [0, 0])
    extras: dict[str, Any] = field(default_factory=dict)

    def align(self):
        """Aligns the channels of the control and target qubits, and the coupler if present."""
        channels = []
        for qubit in [self.qubit_control, self.qubit_target]:
            channels += [ch.name for ch in qubit.channels.values()]

        if self.coupler:
            channels += [self.coupler.name]

        # TODO We should not have a hardcoded macro dependency here
        if "CZ" in self.macros and hasattr(self.macros["CZ"], "compensations"):
            for compensation in self.macros["CZ"].compensations:
                channels += [ch.name for ch in compensation["qubit"].channels.values()]

        align(*channels)

    def wait(self, duration):
        """Waits for the specified duration on the channels of the control and target qubits, and the coupler if present.

        Args:
            duration: The duration to wait in unit of clock cycles (4ns).
        """
        channels = []
        for qubit in [self.qubit_control, self.qubit_target]:
            channels += [ch.name for ch in qubit.channels.values()]

        if self.coupler:
            channels += [self.coupler.name]

        # TODO We should not have a hardcoded macro dependency here
        if "CZ" in self.macros and hasattr(self.macros["CZ"], "compensations"):
            for compensation in self.macros["CZ"].compensations:
                channels += [ch.name for ch in compensation["qubit"].channels.values()]

        wait(duration, *channels)

    def to_mutual_idle(self):
        """Sets the flux bias to the mutual idle offset for the control and target qubits."""
        self.qubit_control.z.set_dc_offset(self.mutual_flux_bias[0])
        self.qubit_target.z.set_dc_offset(self.mutual_flux_bias[1])
