from typing import Union, Tuple

from qm import QuantumMachine
from qm.octave.octave_mixer_calibration import MixerCalibrationResults
from qm import logger

from quam.core import quam_dataclass
from quam.components import InOutSingleChannel

from quam_builder.architecture.quantum_dots.components import ReadoutResonatorIQ, ReadoutResonatorMW, ReadoutResonatorSingle
from quam_builder.architecture.quantum_dots.components import QuantumDot

__all__ = ["SensorDot"]


@quam_dataclass
class SensorDot(QuantumDot):
    """
    Quam component for Sensor Quantum Dot 
    """

    readout_resonator: Union[ReadoutResonatorIQ, ReadoutResonatorMW, ReadoutResonatorSingle]
    state_threshold: float = None


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
