from typing import Dict, Any, Optional, Union, List
from dataclasses import field
from qm.qua import align, wait

from quam.core import quam_dataclass
from quam.components.quantum_components import QubitPair
from quam_builder.architecture.superconducting.components.tunable_coupler import TunableCoupler
from quam_builder.architecture.superconducting.qubit.flux_tunable_transmon import FluxTunableTransmon

__all__ = ["FluxTunableTransmonPair"]


@quam_dataclass
class FluxTunableTransmonPair(QubitPair):
    id: Union[int, str]
    qubit_control: FluxTunableTransmon = None
    qubit_target: FluxTunableTransmon = None

    coupler: Optional[TunableCoupler] = None
    mutual_flux_bias: List[float] = field(default_factory=lambda: [0, 0])
    extras: Dict[str, Any] = field(default_factory=dict)

    def align(self):
        channels = []
        for qubit in [self.qubit_control, self.qubit_target]:
            channels += [ch.name for ch in qubit.channels.values()]

        if self.coupler:
            channels += [self.coupler.name]

        if "Cz" in self.gates:
            if hasattr(self.gates["Cz"], "compensations"):
                for compensation in self.gates["Cz"].compensations:
                    channels += [
                        compensation["qubit"].xy.name,
                        compensation["qubit"].z.name,
                        compensation["qubit"].resonator.name,
                    ]

        align(*channels)

    def wait(self, duration):
        channels = []
        for qubit in [self.qubit_control, self.qubit_target]:
            channels += [ch.name for ch in qubit.channels.values()]

        if self.coupler:
            channels += [self.coupler.name]

        if "Cz" in self.gates:
            if hasattr(self.gates["Cz"], "compensations"):
                for compensation in self.gates["Cz"].compensations:
                    channels += [
                        compensation["qubit"].xy.name,
                        compensation["qubit"].z.name,
                        compensation["qubit"].resonator.name,
                    ]

        wait(duration, *channels)

    def to_mutual_idle(self):
        """Set the flux bias to the mutual idle offset"""
        self.qubit_control.z.set_dc_offset(self.mutual_flux_bias[0])
        self.qubit_target.z.set_dc_offset(self.mutual_flux_bias[1])
