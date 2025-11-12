from typing import Union
from dataclasses import field, asdict

from quam.core import quam_dataclass
from quam.components import InOutSingleChannel

from quam_builder.architecture.quantum_dots.components import (
    ReadoutResonatorIQ,
    ReadoutResonatorMW,
)
from quam_builder.architecture.quantum_dots.components import QuantumDot

__all__ = ["SensorDot", "Projector"]

@quam_dataclass
class Projector:
    wI: float = 1.0
    wQ: float = 0.0
    offset: float = 0.0

@quam_dataclass
class SensorDot(QuantumDot):
    """
    Quam component for Sensor Quantum Dot
    """

    readout_resonator: Union[ReadoutResonatorMW, ReadoutResonatorIQ]
    readout_thresholds: dict = field(default_factory=dict[str, float])
    readout_projectors: dict = field(default_factory=dict[str, dict[str, float]])

    def _add_readout_params(
        self,
        quantum_dot_pair_id: str,
        threshold: float,
        projector: Union[dict, Projector] = None
    ) -> None:
        if projector is None:
            projector = Projector()
        self._add_readout_threshold(quantum_dot_pair_id, threshold)
        self._add_readout_projector(quantum_dot_pair_id, projector)

    def _add_readout_threshold(
        self, quantum_dot_pair_id: str, threshold: float
    ) -> None:
        self.readout_thresholds[quantum_dot_pair_id] = threshold

    def _add_readout_projector(
        self, quantum_dot_pair_id: str, projector: Union[dict, Projector]
    ) -> None:
        if isinstance(projector, Projector):
            projector = asdict(projector)
        self.readout_projectors[quantum_dot_pair_id] = projector

    def _readout_params(
        self, quantum_dot_pair_id: str
    ) -> Union[float, dict[str, float]]:
        return (
            self.readout_thresholds[quantum_dot_pair_id],
            self.readout_projectors[quantum_dot_pair_id],
        )

    def measure(self, *args, **kwargs):
        self.readout_resonator.measure(*args, **kwargs)
