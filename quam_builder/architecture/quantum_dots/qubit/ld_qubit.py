from typing import Dict, Tuple, Union, Literal, TYPE_CHECKING, Optional, List
from dataclasses import field
import numpy as np

from quam.components.quantum_components import Qubit
from quam.components import Channel
from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.components.mixin import VoltageMacroMixin

from qm.octave.octave_mixer_calibration import MixerCalibrationResults
from qm import logger
from qm import QuantumMachine
from qm.qua import wait, frame_rotation_2pi

from quam_builder.architecture.quantum_dots.components import XYDrive

from quam_builder.architecture.quantum_dots.components import QuantumDot, SensorDot

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["LDQubit"]


@quam_dataclass
class LDQubit(Qubit, VoltageMacroMixin):
    """
    An example QUAM component for a Loss DiVincenzo Qubit

    Attributes:
        id: returns the id of the associated QuantumDot
        quantum_dot (QuantumDot): The single QuantumDot instance associated with the Loss DiVincenzo qubit.
        drive (Channel): The QUAM channel associated with the EDSR or ESR line of the qubit.
        T1 (float): The qubit T1 in seconds. Default is None.
        T2ramsey (float): The qubit T2* in seconds.
        T2echo (float): The qubit T2 in seconds.
        thermalization_time_factor (int): Thermalization time in units of T1. Default is 5.
        points (Dict[str, Dict[str, float]]): A dictionary of instantiated macro points.

    Methods:
        go_to_voltages: To be used in a sequence.simultaneous block for simultaneous stepping/ramping to a particular voltage.
        step_to_voltages: Enters a dictionary to the VoltageSequence to step to the particular voltage.
        ramp_to_voltages: Enters a dictionary to the VoltageSequence to ramp to the particular voltage.
        calibrate_octave: Calibrates the Octave channels (xy and resonator) linked to this transmon.
        thermalization_time: Returns the Loss DiVincenzo Qubit thermalization time in ns.
        reset: Reset the qubit state with a specified reset type. Default is thermal (wait thermalization time).
        add_point: Adds a point macro to the associated VirtualGateSet. Also registers said point in the internal points attribute. Can accept qubit names
        step_to_point: Steps to a pre-defined point in the internal points dict.
        ramp_to_point: Ramps to a pre-defined point in the internal points dict.
    """

    id: Union[str, int] = None
    grid_location: str = None

    quantum_dot: QuantumDot
    xy_channel: XYDrive = None

    larmor_frequency: float = None

    # Qubit Specific Features
    T1: float = None
    T2ramsey: float = None
    T2echo: float = None
    thermalization_time_factor: int = 5

    points: Dict[str, Dict[str, float]] = field(default_factory=dict)

    name: str = None
    _preferred_readout_quantum_dot: str = None

    def __post_init__(self):
        if isinstance(self.quantum_dot, str):
            return
        if self.id is None:
            self.id = self.quantum_dot.id
        # if self.id != self.quantum_dot.id:
        #     raise ValueError(
        #         f"LDQubit id {self.id} does not match QuantumDot id {self.quantum_dot.id}. "
        #         f"These must be consistent. Either set LDQubit(id = {self.quantum_dot.id}, ...)"
        #     )

    @property
    def physical_channel(self) -> Channel:
        return self.quantum_dot.physical_channel

    @property
    def machine(self) -> "BaseQuamQD":
        return self.quantum_dot.machine

    @property
    def thermalization_time(self):
        """The transmon thermalization time in ns."""
        if self.T1 is not None:
            return int(self.thermalization_time_factor * self.T1 * 1e9 / 4) * 4
        else:
            return int(self.thermalization_time_factor * 10e-6 * 1e9 / 4) * 4

    @property
    def voltage_sequence(self):
        return self.quantum_dot.voltage_sequence

    def _get_component_id_for_voltages(self) -> str:
        """Target the quantum_dot for voltage operations."""
        return self.quantum_dot.id

    # Voltage and point methods (go_to_voltages, step_to_voltages, ramp_to_voltages,
    # add_point, step_to_point, ramp_to_point) are now provided by VoltageMacroMixin
    def _validate_readout_quantum_dot(self, qd_name):
        """Validate that the preferred quantum dot for readout actually exists in Quam, and forms a QuantumDotPair with the QuantumDot in this LDQubit."""
        if qd_name not in self.machine.quantum_dots:
            raise ValueError(f"Quantum Dot {qd_name} not a registered Quantum Dot in Quam. ")
        qd_pair = self.machine.find_quantum_dot_pair(self.quantum_dot.id, qd_name)
        if qd_pair is None:
            raise ValueError(
                f"Quantum dots {self.quantum_dot.id} and {qd_name} are not a registered Quantum Dot Pair. Please register first"
            )

    @property
    def preferred_readout_quantum_dot(self) -> str:
        return self._preferred_readout_quantum_dot

    @preferred_readout_quantum_dot.setter
    def preferred_readout_quantum_dot(self, value: str):
        if value is not None and not isinstance(self.quantum_dot, str):
            self._validate_readout_quantum_dot(value)
        self._preferred_readout_quantum_dot = value

    @property
    def sensor_dots(self) -> List[SensorDot]:
        if self._preferred_readout_quantum_dot is None:
            raise ValueError(
                f"No preferred_readout_quantum_dot set for qubit '{self.id}'. Please set first"
            )
        self._validate_readout_quantum_dot(self._preferred_readout_quantum_dot)
        qd_pair = self.machine.quantum_dot_pairs[
            self.machine.find_quantum_dot_pair(
                self.quantum_dot.id, self.preferred_readout_quantum_dot
            )
        ]
        sensors = qd_pair.sensor_dots
        return sensors

    def calibrate_octave(
        self,
        QM: QuantumMachine,
        calibrate_drive: bool = True,
    ) -> Tuple[Union[None, MixerCalibrationResults], Union[None, MixerCalibrationResults]]:
        """Calibrate the Octave channels (EDSR and possible resonator) linked to this qubit for the LO frequency, intermediate
        frequency and Octave gain as defined in the state.

        Args:
            QM (QuantumMachine): the running quantum machine.
            calibrate_drive (bool): flag to calibrate xy line.

        Return:
            The Octave calibration results as (drive)
        """

        if calibrate_drive and self.drive is not None:
            if hasattr(self.drive, "frequency_converter_up"):
                logger.info(f"Calibrating {self.drive.name}")
                drive_calibration_output = QM.calibrate_element(
                    self.drive.name,
                    {
                        self.drive.frequency_converter_up.LO_frequency: (
                            self.drive.intermediate_frequency,
                        )
                    },
                )
            else:
                raise RuntimeError(
                    f"{self.drive.name} doesn't have a 'frequency_converter_up' attribute, it is thus most likely not "
                    "connected to an Octave."
                )
        else:
            drive_calibration_output = None
        return drive_calibration_output

    def reset(
        self,
        reset_type: Literal["thermal"] = "thermal",
    ):

        if reset_type == "thermal":
            self.reset_qubit_thermal()

    def reset_qubit_thermal(self):
        """
        Perform a thermal reset of the qubit.

        This function waits for a duration specified by the thermalization time
        to allow the qubit to return to its ground state through natural thermal
        relaxation.
        """
        self.wait(self.thermalization_time // 4)

    def wait(self, duration: int):
        """Wait for a given duration on all channels of the qubit.

        Args:
            duration (int): The duration to wait for in unit of clock cycles (4ns).
        """
        channel_names = [channel.name for channel in self.channels.values()]
        wait(duration, *channel_names)

    def add_xy_pulse(self, pulse_name: str, pulse) -> None:
        self.xy_channel.add_pulse(name=pulse_name, pulse=pulse)

    def set_xy_frequency(self, frequency: float, recenter_LO: bool = True):
        """
        Configure the LO+IF of the xy_channel. Use this function to update the drive frequency to the calibrated Larmor frequency
        """
        if self.xy_channel is None:
            raise ValueError(f"No XY Channel on Qubit {self.id}")

        LO_frequency = self.xy_channel.LO_frequency
        intermediate_frequency = frequency - LO_frequency

        if abs(intermediate_frequency) > 400e6:
            if recenter_LO:
                print(
                    f"Intermediate Frequency exceeds ±400MHz ({intermediate_frequency/1e6 : .2f}MHz). Setting LO to {frequency/1e9: .4f}GHz"
                )
                self.xy_channel.LO_frequency = frequency
                self.xy_channel.intermediate_frequency = 0
            else:
                raise ValueError(
                    f"Intermediate Frequency ({intermediate_frequency/1e6 : .2f}MHz) exceeds ±400MHz"
                )
        else:
            self.xy_channel.intermediate_frequency = intermediate_frequency

    def play_xy_pulse(
        self,
        pulse_name: str,
        pulse_duration: Optional[int] = None,
        amplitude_scale: float = None,
        **kwargs,
    ) -> None:
        """Play a pulse from the XY channel associated with the Qubit"""
        if self.xy_channel is None:
            raise ValueError(f"No XY Channel on Qubit {self.id}")

        if pulse_name not in self.xy_channel.operations:
            raise ValueError(f"Pulse {pulse_name} not in XY Channel operations")

        self.xy_channel.play(
            pulse_name=pulse_name,
            amplitude_scale=amplitude_scale,
            duration=pulse_duration,
            **kwargs,
        )

    def virtual_z(self, phase: float) -> None:
        """Apply a virtual Z rotation"""
        frame_rotation_2pi(phase / (2 * np.pi), self.xy_channel.name)
