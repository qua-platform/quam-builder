"""Sensor dot components for quantum dot systems."""

# pylint: disable=invalid-field-call,unsupported-assignment-operation,unsubscriptable-object,too-few-public-methods

from dataclasses import asdict, field
from typing import Tuple, Union

from qm import QuantumMachine, logger
from qm.octave.octave_mixer_calibration import MixerCalibrationResults

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.components.readout_resonator import (
    ReadoutResonatorIQ,
    ReadoutResonatorMW,
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.components.quantum_dot import QuantumDot

__all__ = ["SensorDot", "Projector"]


@quam_dataclass
class Projector:
    """Projection weights for IQ readout."""

    wI: float = 1.0
    wQ: float = 0.0
    offset: float = 0.0


@quam_dataclass
class SensorDot(QuantumDot):
    """
    Quam component for Sensor Quantum Dot.
    """

    readout_resonator: Union[
        ReadoutResonatorMW,
        ReadoutResonatorIQ,
        ReadoutResonatorSingle,
    ]
    readout_thresholds: dict[str, float] = field(default_factory=dict)
    readout_projectors: dict[str, dict[str, float]] = field(default_factory=dict)

    def _add_readout_params(
        self,
        quantum_dot_pair_id: str,
        threshold: float,
        projector: Union[dict, Projector] = None,
    ) -> None:
        """Register threshold and projector for a quantum dot pair."""
        if projector is None:
            projector = Projector()
        self._add_readout_threshold(quantum_dot_pair_id, threshold)
        self._add_readout_projector(quantum_dot_pair_id, projector)

    def _add_readout_threshold(self, quantum_dot_pair_id: str, threshold: float) -> None:
        """Store readout threshold for a quantum dot pair."""
        self.readout_thresholds[quantum_dot_pair_id] = threshold

    def _add_readout_projector(
        self, quantum_dot_pair_id: str, projector: Union[dict, Projector]
    ) -> None:
        """Store readout projector for a quantum dot pair."""
        if isinstance(projector, Projector):
            projector = asdict(projector)
        self.readout_projectors[quantum_dot_pair_id] = projector

    def _readout_params(self, quantum_dot_pair_id: str) -> Union[float, dict[str, float]]:
        """Return readout threshold and projector for a quantum dot pair."""
        return (
            self.readout_thresholds[quantum_dot_pair_id],
            self.readout_projectors[quantum_dot_pair_id],
        )

    def measure(self, *args, **kwargs):
        """Delegate measurement to the readout resonator."""
        self.readout_resonator.measure(*args, **kwargs)

    def calibrate_octave(
        self,
        QM: QuantumMachine,
        calibrate_resonator: bool = True,
    ) -> Tuple[Union[None, MixerCalibrationResults], Union[None, MixerCalibrationResults]]:
        """Calibrate Octave channels linked to this qubit for LO frequency and gain.

        Args:
            QM (QuantumMachine): the running quantum machine.
            calibrate_resonator (bool): flag to calibrate resonator line.
        Return:
            The Octave calibration results as (drive)
        """

        if calibrate_resonator and self.readout_resonator is not None:
            if hasattr(self.readout_resonator, "frequency_converter_up"):
                logger.info(f"Calibrating {self.readout_resonator.name}")
                resonator_calibration_output = QM.calibrate_element(
                    self.readout_resonator.name,
                    {
                        self.readout_resonator.frequency_converter_up.LO_frequency: (
                            self.readout_resonator.intermediate_frequency,
                        )
                    },
                )
            else:
                raise RuntimeError(
                    f"{self.readout_resonator.name} doesn't have a "
                    "'frequency_converter_up' attribute, it is thus most likely "
                    "not connected to an Octave."
                )
        else:
            resonator_calibration_output = None

        return resonator_calibration_output
