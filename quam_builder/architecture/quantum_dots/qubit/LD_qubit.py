from typing import List, Dict, Tuple, Union, Literal
from dataclasses import field

from quam.components.quantum_components import Qubit
from quam.components import Channel
from quam.core import quam_dataclass

from qm.octave.octave_mixer_calibration import MixerCalibrationResults
from qm import logger
from qm import QuantumMachine
from qm.qua.type_hints import QuaVariable
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

from quam_builder.architecture.quantum_dots.components import QuantumDot


__all__ = ["LDQubit"]


@quam_dataclass
class LDQubit(Qubit):
    """
    An example QUAM component for a Loss DiVincenzo Qubit

    Attributes:
        quantum_dot (QuantumDot): The single QuantumDot instance associated with the Loss DiVincenzo qubit. 
        drive (Channel): The QUAM channel associated with the EDSR or ESR line of the qubit. 
        T1 (float): The qubit T1 in seconds. Default is None.
        T2ramsey (float): The qubit T2* in seconds.
        T2echo (float): The qubit T2 in seconds.
        thermalization_time_factor (int): Thermalization time in units of T1. Default is 5.

    Methods: 
        id: returns the id of the associated QuantumDot
        go_to_voltages: To be used in a sequence.simultaneous block for simultaneous stepping/ramping to a particular voltage.
        step_to_voltages: Enters a dictionary to the VoltageSequence to step to the particular voltage.  
        ramp_to_voltages: Enters a dictionary to the VoltageSequence to ramp to the particular voltage.  
        calibrate_octave: Calibrates the Octave channels (xy and resonator) linked to this transmon.
        thermalization_time: Returns the Loss DiVincenzo Qubit thermalization time in ns.
    """
    id: Union[str, int] = None

    quantum_dot: QuantumDot
    drive: Channel = None

    # Qubit Specific Features
    T1: float = None
    T2ramsey: float = None
    T2echo: float = None
    thermalization_time_factor: int = 5

    points: Dict[str, Dict[str, float]] = field(default_factory=dict)

    name: str = None

    def __post_init__(self): 
        if self.id is None: 
            self.id = self.quantum_dot.id
        if self.id != self.quantum_dot.id:
            raise ValueError(
                f"LDQubit id {self.id} does not match QuantumDot id {self.quantum_dot.id}. "
                f"These must be consistent. Either set LDQubit(id = {self.quantum_dot.id}, ...)"
            )
    
    @property
    def physical_channel(self): 
        return self.quantum_dot.physical_channel
    
    
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

    def step_to_voltages(self, voltage:float, duration:int = 16) -> None: 
        return self.quantum_dot.step_to_voltages(voltage, duration = duration)
    
    def ramp_to_voltages(self, voltage:float, ramp_duration: int, duration:int = 16) -> None: 
        return self.quantum_dot.step_to_voltages(voltage, ramp_duration = ramp_duration, duration = duration)
    
    def go_to_voltages(self, voltage:float, duration:int = 16) -> None: 
        return self.quantum_dot.go_to_voltages(voltage, duration = duration)

    def initialisation(self): 
        # self.voltage_sequence.step_to_voltages("Qubit1_Idle")
        # self.voltage_sequence.step_to_voltages("Qubit1_Idle2")
        # self.voltage_sequence.step_to_voltages("Qubit1_Idle3")
        pass

    def calibrate_octave(
        self,
        QM: QuantumMachine,
        calibrate_drive: bool = True,
    ) -> Tuple[
        Union[None, MixerCalibrationResults], Union[None, MixerCalibrationResults]
    ]:
        """Calibrate the Octave channels (EDSR and possible resonator) linked to this qubit for the LO frequency, intermediate
        frequency and Octave gain as defined in the state.

        Args:
            QM (QuantumMachine): the running quantum machine.
            calibrate_drive (bool): flag to calibrate xy line.

        Return:
            The Octave calibration results as (drive)
        """
        ### HASHING OUT FOR NOW. We must think about the resonator architecture

        # if calibrate_resonator and self.resonator is not None:
        #     if hasattr(self.resonator, "frequency_converter_up"):
        #         logger.info(f"Calibrating {self.resonator.name}")
        #         resonator_calibration_output = QM.calibrate_element(
        #             self.resonator.name,
        #             {
        #                 self.resonator.frequency_converter_up.LO_frequency: (
        #                     self.resonator.intermediate_frequency,
        #                 )
        #             },
        #         )
        #     else:
        #         raise RuntimeError(
        #             f"{self.resonator.name} doesn't have a 'frequency_converter_up' attribute, it is thus most likely "
        #             "not connected to an Octave."
        #         )
        # else:
        #     resonator_calibration_output = None

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

    def wait(self, duration:int): 
        """Wait for a given duration on all channels of the qubit.

        Args:
            duration (int): The duration to wait for in unit of clock cycles (4ns).
        """
        channel_names = [channel.name for channel in self.channels.values()]
        wait(duration, *channel_names)

    def add_point(self, point_name:str, voltages: Dict[str, float], duration: int = 16, replace_existing_point: bool = False) -> None: 
        """
        Add a point macro to the VirtualGateSet associated with the qubit. 
        
        Args: 
            point_name (str): The name of the point macro
            voltages (Dict[str, float]): A dictionary of voltages to enter into the VirtualGateSet. This can include qubit names and QD names, as well as 
                                            any virtualised axis in the VirtualGateSet. Internally, qubit names are converted to the names of the associated quantum dots. 
            duration (int): The duration which to hold the point. 
            replace_existing_point (bool): If the point_name is the same as a previously added point, choose whether to replace old point. Will raise an error if False. 
        """
        name_in_sequence = f"{self.name}_{point_name}"
        # In-case there are any qubit names in the input dictionary, this must be mapped to the correct quantum dot gate name in the VirtualGateSet
        processed_voltages = {}
        qubit_mapping = self.parent
        for gate_name, voltage in voltages.items(): 
            if gate_name in qubit_mapping: 
                gate_name = qubit_mapping[gate_name].id
            processed_voltages[gate_name] = voltage

        gate_set = self.voltage_sequence.gate_set
        existing_points = gate_set.get_macros()

        if name_in_sequence in existing_points and not replace_existing_point: 
            raise ValueError(f"Point name {point_name} already exists for qubit {self.name}. If you would like to replace, please set replace_existing_point = True")
        self.points[point_name] = voltages
        gate_set.add_point(
            name = name_in_sequence, 
            voltages = processed_voltages, 
            duration = duration
        )
        
    def step_to_point(self, point_name: str, duration:int = 16) -> None: 
        """Step to a point registered for the qubit"""
        if point_name not in self.points: 
            raise ValueError(f"Point {point_name} not in registered points: {list(self.points.keys())}")
        name_in_sequence = f"{self.name}_{point_name}"
        return self.voltage_sequence.step_to_point(name = name_in_sequence, duration = duration)
    
    def ramp_to_point(self, point_name: str, ramp_duration:int,  duration:int = 16) -> None: 
        """Ramp to a point registered for the qubit"""
        if point_name not in self.points: 
            raise ValueError(f"Point {point_name} not in registered points: {list(self.points.keys())}")
        name_in_sequence = f"{self.name}_{point_name}"
        return self.voltage_sequence.ramp_to_point(name = name_in_sequence, duration = duration, ramp_duration=ramp_duration)

