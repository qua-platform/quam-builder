from typing import Dict, Any, Union, Tuple
from dataclasses import field

from quam.core import quam_dataclass
from quam.components.quantum_components import Qubit
from quam_builder.architecture.superconducting.components.xy_drive import (
    XYDriveIQ,
    XYDriveMW,
)

from qm import QuantumMachine, logger
from qm.octave.octave_mixer_calibration import MixerCalibrationResults
from qm.qua import wait


__all__ = ["BosonicMode"]


@quam_dataclass
class BosonicMode(Qubit):
    """
    QUAM component for a bosonic mode (harmonic cavity).

    Unlike transmons which are anharmonic oscillators, bosonic modes are harmonic
    oscillators with equally spaced energy levels. This component represents a
    cavity mode that can be driven via an XY drive.

    Attributes:
        id (Union[int, str]): The id of the cavity, used to generate the name.
            Can be a string, or an integer in which case it will add `Channel._default_label`.
        xy (Union[XYDriveIQ, XYDriveMW]): The xy drive component for cavity control.
        frequency (float): The cavity frequency in Hz. Default is None.
        T1 (float): The cavity T1 (energy relaxation time) in seconds. Default is None.
        T2ramsey (float): The cavity T2* (dephasing time) in seconds. Default is None.
        T2echo (float): The cavity T2 (echo time) in seconds. Default is None.
        thermalization_time_factor (int): Thermalization time in units of T1. Default is 5.
        grid_location (str): Cavity location in the plot grid as "column, row".
        extras (Dict[str, Any]): Additional attributes for the cavity.

    Methods:
        thermalization_time: Returns the cavity thermalization time in ns.
        calibrate_octave: Calibrates the Octave channel (xy drive) linked to this cavity.
        wait: Wait for a given duration on all channels of the cavity.
    """

    id: Union[int, str]

    xy: Union[XYDriveIQ, XYDriveMW] = None
    frequency: float = None

    T1: float = None
    T2ramsey: float = None
    T2echo: float = None
    thermalization_time_factor: int = 5

    grid_location: str = None
    extras: Dict[str, Any] = field(default_factory=dict)

    @property
    def thermalization_time(self):
        """The cavity thermalization time in ns."""
        if self.T1 is not None:
            return int(self.thermalization_time_factor * self.T1 * 1e9 / 4) * 4
        else:
            return int(self.thermalization_time_factor * 10e-6 * 1e9 / 4) * 4

    def calibrate_octave(
        self,
        QM: QuantumMachine,
        calibrate_drive: bool = True,
    ) -> Tuple[Union[None, MixerCalibrationResults]]:
        """Calibrate the Octave channel (xy drive) linked to this cavity for the LO frequency,
        intermediate frequency and Octave gain as defined in the state.

        Args:
            QM (QuantumMachine): the running quantum machine.
            calibrate_drive (bool): flag to calibrate xy line.

        Return:
            The Octave calibration result for the xy drive (or None if not calibrated).
        """
        if calibrate_drive and self.xy is not None:
            if hasattr(self.xy, "frequency_converter_up"):
                logger.info(f"Calibrating {self.xy.name}")
                xy_drive_calibration_output = QM.calibrate_element(
                    self.xy.name,
                    {
                        self.xy.frequency_converter_up.LO_frequency: (
                            self.xy.intermediate_frequency,
                        )
                    },
                )
            else:
                raise RuntimeError(
                    f"{self.xy.name} doesn't have a 'frequency_converter_up' attribute, it is thus most likely not "
                    "connected to an Octave."
                )
        else:
            xy_drive_calibration_output = None
        return xy_drive_calibration_output

    def wait(self, duration: int):
        """Wait for a given duration on all channels of the cavity.

        Args:
            duration (int): The duration to wait for in unit of clock cycles (4ns).
        """
        channel_names = [channel.name for channel in self.channels.values()]
        wait(duration, *channel_names)
