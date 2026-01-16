from typing import Union, Tuple
from dataclasses import field, asdict

from qm import QuantumMachine
from qm.octave.octave_mixer_calibration import MixerCalibrationResults
from qm import logger

from quam.core import quam_dataclass
from quam.components import InOutSingleChannel

from .readout_resonator import (
    ReadoutResonatorIQ,
    ReadoutResonatorMW,
    ReadoutResonatorSingle
)
from .quantum_dot import QuantumDot

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

    readout_resonator: Union[ReadoutResonatorMW, ReadoutResonatorIQ, ReadoutResonatorSingle]
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

    def calibrate_octave(
            self,
            QM: QuantumMachine,
            calibrate_resonator: bool = True,
        ) -> Tuple[
            Union[None, MixerCalibrationResults], Union[None, MixerCalibrationResults]
        ]:
            """Calibrate the Octave channels (EDSR and possible resonator) linked to this qubit for the LO frequency, intermediate
            frequency and Octave gain as defined in the state.
            Args:
                QM (QuantumMachine): the running quantum machine.
                calibrate_resonator (bool): flag to calibrate resaontor line.
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
                        f"{self.readout_resonator.name} doesn't have a 'frequency_converter_up' attribute, it is thus most likely "
                        "not connected to an Octave."
                    )
            else:
                resonator_calibration_output = None

            return resonator_calibration_output