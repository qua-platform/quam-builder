from typing import Callable, Dict, Any, Union, Optional, Literal, Tuple
from dataclasses import field
from logging import getLogger

from quam.core import quam_dataclass
from quam.components.quantum_components import Qubit
from quam_builder.architecture.nv_center.components.spcm import SPCM
from quam_builder.architecture.nv_center.components.laser import LaserControl
from quam_builder.architecture.nv_center.components.xy_drive import (
    XYDriveIQ,
    XYDriveMW,
)

from qm import QuantumMachine, logger
from qm.qua.type_hints import QuaVariable
from qm.octave.octave_mixer_calibration import MixerCalibrationResults
from qm.qua import (
    save,
    declare,
    fixed,
    assign,
    wait,
    while_,
    StreamType,
    if_,
    update_frequency,
    Math,
    Cast,
)

__all__ = ["NVCenter"]


@quam_dataclass
class NVCenter(Qubit):
    """
    Example QUAM component for a transmon qubit.

    Attributes:
        id (Union[int, str]): The id of the NV center, used to generate the name.
            Can be a string, or an integer in which case it will add `Channel._default_label`.
        xy (Union[MWChannel, IQChannel]): The xy drive component.
        spcm1 (SPCM): The first detector component.
        spcm2 (SPCM): A second detector component.
        T1 (float): The transmon T1 in seconds. Default is None.
        T2ramsey (float): The transmon T2* in seconds.
        T2echo (float): The transmon T2 in seconds.
        gate_fidelity (Dict[str, Any]): Collection of single qubit gate fidelity.
        extras (Dict[str, Any]): Additional attributes for the transmon.

    Methods:
        name: Returns the name of the NV center.
        readout_state: Performs a readout of the qubit state using the specified pulse.
        reset_qubit: Reset the qubit to the ground state ('g') with the specified method.
        reset_qubit_thermal: Reset the qubit to the ground state ('g') using thermalization.
    """

    id: Union[int, str]

    xy: Union[XYDriveIQ, XYDriveMW] = None
    laser: LaserControl = None
    spcm1: SPCM = None

    f_01: float = None

    T1: float = None
    T2ramsey: float = None
    T2echo: float = None

    grid_location: str = None
    gate_fidelity: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)

    def calibrate_octave(
        self,
        QM: QuantumMachine,
        calibrate_drive: bool = True,
        calibrate_resonator: bool = False,
    ) -> Tuple[
        Union[None, MixerCalibrationResults], Union[None, MixerCalibrationResults]
    ]:
        """Calibrate the Octave channels (xy and resonator) linked to this NV center for the LO frequency, intermediate
        frequency and Octave gain as defined in the state.

        Args:
            QM (QuantumMachine): the running quantum machine.
            calibrate_drive (bool): flag to calibrate xy line.
            calibrate_resonator (bool): flag to calibrate the resonator line.

        Return:
            The Octave calibration results as (resonator, xy_drive)
        """
        if calibrate_resonator and self.resonator is not None:
            if hasattr(self.resonator, "frequency_converter_up"):
                logger.info(f"Calibrating {self.resonator.name}")
                resonator_calibration_output = QM.calibrate_element(
                    self.resonator.name,
                    {
                        self.resonator.frequency_converter_up.LO_frequency: (
                            self.resonator.intermediate_frequency,
                        )
                    },
                )
            else:
                raise RuntimeError(
                    f"{self.resonator.name} doesn't have a 'frequency_converter_up' attribute, it is thus most likely "
                    "not connected to an Octave."
                )
        else:
            resonator_calibration_output = None

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
        return resonator_calibration_output, xy_drive_calibration_output

    def set_gate_shape(self, gate_shape: str) -> None:
        """Set the shape fo the single qubit gates defined as ["x180", "x90" "-x90", "y180", "y90", "-y90"]"""
        for gate in ["x180", "x90", "-x90", "y180", "y90", "-y90"]:
            if f"{gate}_{gate_shape}" in self.xy.operations:
                self.xy.operations[gate] = f"#./{gate}_{gate_shape}"
            else:
                raise AttributeError(
                    f"The gate '{gate}_{gate_shape}' is not part of the existing operations for {self.xy.name} --> {self.xy.operations.keys()}."
                )

    def readout_state(self, state, readout_name: str = "readout"):
        """
        Perform a readout of the qubit state using the specified pulse.

        This function measures the qubit state using the specified readout pulse and assigns the result to the given state variable.

        Args:
            state: The variable to assign the readout result to.
            readout_name (str): The name of the readout pulse to use. Default is "readout".

        Returns:
            None

        The function declares integer variables times and counts, measures the qubit state using the specified pulse with time tagging, and assigns the count result to the state variable.
        """
        times = declare(int, size=100)
        counts = declare(int)
        self.spcm1.measure_time_tagging(
            readout_name,
            size=100,
            max_time=self.spcm1.operations[readout_name].length,
            qua_vars=(times, counts),
            mode="analog",
        )
        assign(state, counts)

    def reset(
        self,
        reset_type: Literal["laser"] = "laser",
        simulate: bool = False,
        log_callable: Optional[Callable] = None,
        **kwargs,
    ):
        """
        Reset the qubit with the specified method.

        This function resets the qubit using the specified method: laser reset.
        When simulating the QUA program, the qubit reset is skipped to save simulated samples.

        Args:
            reset_type (Literal["laser"]): The type of reset to perform. Default is "laser".
            simulate (bool): If True, the qubit reset is skipped for simulation purposes. Default is False.
            log_callable (optional): Logger instance to log warnings. If None, a default logger is used.
            **kwargs: Additional keyword arguments passed to the active reset methods.

        Returns:
            None

        Raises:
            Warning: If the function is called in simulation mode, a warning is issued indicating
                     that the qubit reset has been skipped.
        """
        if not simulate:
            if reset_type == "laser":
                self.reset_qubit_laser(**kwargs)
            else:
                raise NotImplementedError(f"Reset type {reset_type} is not implemented.")
        else:
            if log_callable is None:
                log_callable = getLogger(__name__).warning
            log_callable(
                "For simulating the QUA program, the qubit reset has been skipped."
            )

    def reset_qubit_laser(self, **kwargs):
        """
        Perform a laser reset of the qubit.

        This function waits for a duration specified by the laser pumping time
        to allow the qubit to return to its ground state through laser pumping.
        """
        self.laser.play("laser_on")

    def wait(self, duration: int):
        """Wait for a given duration on all channels of the qubit.

        Args:
            duration (int): The duration to wait for in unit of clock cycles (4ns).
        """
        channel_names = [channel.name for channel in self.channels.values()]
        wait(duration, *channel_names)
