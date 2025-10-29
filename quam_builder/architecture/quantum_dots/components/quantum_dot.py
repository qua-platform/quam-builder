import numpy as np
from dataclasses import field
from typing import Dict, Union, Tuple, Optional, List, Sequence, TYPE_CHECKING

from quam.core import quam_dataclass, QuamComponent
from quam.components import Channel
from quam.utils.qua_types import (
    ChirpType,
    StreamType,
    ScalarInt,
    ScalarFloat,
    ScalarBool,
    QuaScalarInt,
    QuaVariableInt,
    QuaVariableFloat,
)

from qm import QuantumMachine

from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.tools.voltage_sequence import VoltageSequence
if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["QuantumDot"]


@quam_dataclass
class QuantumDot(QuamComponent):
    """
    Quam component for a single Quantum Dot
    Attributes: 
        id (str): The id of the QuantumDot
        physical_channel (VoltageGate): The VoltageGate instance directly coupled to the QuantumDot.
        current_voltage (float): The current voltage offset of the QuantumDot via the OPX. Default is zero. 
        voltage_sequence (VoltageSeqence): The VoltageSequence object of the associated VirtualGateSet.
        charge_number (int): The integer number of charges currently on the QuantumDot.
        points (Dict[str, Dict[str, float]]): A dictionary of instantiated macro points.

    Methods: 
        go_to_voltages: To be used in a sequence.simultaneous block for simultaneous stepping/ramping to a particular voltage.
        step_to_voltages: Enters a dictionary to the VoltageSequence to step to the particular voltage.  
        ramp_to_voltages: Enters a dictionary to the VoltageSequence to ramp to the particular voltage.  
        get_offset: Returns the current value of the external voltage source. 
        set_offset: Sets the external voltage source to the new value.
        add_point: Adds a point macro to the associated VirtualGateSet. Also registers said point in the internal points attribute. Can NOT accept qubit names 
        step_to_point: Steps to a pre-defined point in the internal points dict. 
        ramp_to_point: Ramps to a pre-defined point in the internal points dict. 
    """
    id: Union[int, str]
    physical_channel: VoltageGate
    charge_number: int = 0
    current_voltage: float = 0.0

    points: Dict[str, Dict[str, float]] = field(default_factory = dict)

    @property
    def name(self) -> str: 
        return self.id if isinstance(self.id, str) else f"dot{self.id}"
    
    @property
    def machine(self) -> "BaseQuamQD":
        # Climb up the parent ladder in order to find the VoltageSequence in the machine
        obj = self
        while obj.parent is not None: 
            obj = obj.parent
        machine = obj
        return machine

    @property
    def voltage_sequence(self) -> VoltageSequence: 
        machine = self.machine
        try: 
            virtual_gate_set_name = machine._get_virtual_gate_set(self.physical_channel).id
            return machine.get_voltage_sequence(virtual_gate_set_name)
        except (AttributeError, ValueError, KeyError): 
            return None

    def go_to_voltages(self, voltage:float, duration:int = 16) -> None:
        """Agnostic function to be used in sequence.simultaneous block. Whether it is a step or a ramp should be determined by the context manager"""

        if self.voltage_sequence is None: 
            raise RuntimeError(f"QuantumDot {self.id} has no VoltageSequence. Ensure that the VoltageSequence is mapped to the" + 
                               " relevant QUAM voltage_sequence.")
        target_voltages = {self.id : voltage}
        return self.voltage_sequence.step_to_voltages(target_voltages, duration = duration)
        

    def step_to_voltages(self, voltage: float, duration:int = 16, preserve_other_gates: bool = False) -> None:
        """
        Applies self.voltage_sequence.step_to_voltages({self.id: voltage})

        The VoltageSequence forms part of the VirtualGateSet, and so feeding the votlage_sequence the name of the 
        QuantumDot id (internally == the VirtualGateSet axis name), should internally resolve this dictionary. 
        """
        if self.voltage_sequence is None: 
            raise RuntimeError(f"QuantumDot {self.id} has no VoltageSequence. Ensure that the VoltageSequence is mapped to the" + 
                               " relevant QUAM voltage_sequence.")
        target_voltages = {}
        if preserve_other_gates:
            for layer in self.voltage_sequence.gate_set.layers: 
                if self.id in layer.source_gates: 
                    physical_voltages = [
                        self.voltage_sequence.state_trackers[target_gate].current_level 
                        for target_gate in layer.target_gates
                    ]
                    matrix = np.array(layer.matrix)

                    virtual_voltages = matrix @ physical_voltages

                    for i, source_gate in enumerate(layer.source_gates):
                        target_voltages[source_gate] = virtual_voltages[i]
                    break

        target_voltages[self.id] = voltage

        return self.voltage_sequence.step_to_voltages(target_voltages, duration = duration)
    
    def ramp_to_voltages(self, voltage: float, ramp_duration: int, duration:int = 16, preserve_other_gates: bool = False) -> None:
        """
        Applies self.voltage_sequence.ramp_to_voltages({self.id: voltage}, ramp_duration = ramp_duration)

        The VoltageSequence forms part of the VirtualGateSet, and so feeding the votlage_sequence the name of the 
        QuantumDot id (internally == the VirtualGateSet axis name), should internally resolve this dictionary. 
        """
        if self.voltage_sequence is None: 
            raise RuntimeError(f"QuantumDot {self.id} has no VoltageSequence. Ensure that the VoltageSequence is mapped to the" + 
                               " relevant QUAM voltage_sequence.")
        target_voltages = {}
        if preserve_other_gates:
            for layer in self.voltage_sequence.gate_set.layers: 
                if self.id in layer.source_gates: 
                    physical_voltages = [
                        self.voltage_sequence.state_trackers[target_gate].current_level 
                        for target_gate in layer.target_gates
                    ]
                    matrix = np.array(layer.matrix)

                    virtual_voltages = matrix @ physical_voltages

                    for i, source_gate in enumerate(layer.source_gates):
                        target_voltages[source_gate] = virtual_voltages[i]
                    break

        target_voltages[self.id] = voltage
        return self.voltage_sequence.ramp_to_voltages(target_voltages, ramp_duration = ramp_duration, duration = duration)
    
    def get_offset(self): 
        v = getattr(self.physical_channel, "offset_parameter", None)
        return float(v()) if callable(v) else 0.0
    
    def set_offset(self, value: float): 
        if self.physical_channel.offset_parameter is not None: 
            self.physical_channel.offset_parameter(value)
            return 
        raise ValueError("External offset source not connected")
    
    def add_point(self, point_name:str, voltages: Dict[str, float], duration: int = 16, replace_existing_point: bool = False) -> None: 
        """
        Method to add point to the VirtualGateSet for the quantum dot.

        Args: 
            point_name (str): The name of the point in the VirtualGateSet
            voltages (Dict[str, float]): A dictionary of the associated voltages. This will NOT be able to read qubit names. 
            duration (int): The duration which to hold the point. 
            replace_existing_point (bool): If the point_name is the same as a previously added point, choose whether to replace old point. Will raise an error if False. 
        """

        gate_set = self.voltage_sequence.gate_set
        existing_points = gate_set.get_macros()
        name_in_sequence = f"{self.id}_{point_name}"
        if name_in_sequence in existing_points and not replace_existing_point: 
            raise ValueError(f"Point name {point_name} already exists for quantum dot {self.id}. If you would like to replace, please set replace_existing_point = True")
        self.points[point_name] = voltages
        gate_set.add_point(
            name = name_in_sequence, 
            voltages = voltages, 
            duration = duration
        )
        
    def step_to_point(self, point_name: str, duration:int = 16) -> None: 
        """Step to a point registered for the quantum dot"""
        if point_name not in self.points: 
            raise ValueError(f"Point {point_name} not in registered points: {list(self.points.keys())}")
        name_in_sequence = f"{self.id}_{point_name}"
        return self.voltage_sequence.step_to_point(name = name_in_sequence, duration = duration)
    
    def ramp_to_point(self, point_name: str, ramp_duration:int,  duration:int = 16) -> None: 
        """Ramp to a point registered for the quantum dot"""
        if point_name not in self.points: 
            raise ValueError(f"Point {point_name} not in registered points: {list(self.points.keys())}")
        name_in_sequence = f"{self.id}_{point_name}"
        return self.voltage_sequence.ramp_to_point(name = name_in_sequence, duration = duration, ramp_duration=ramp_duration)


    def play(    
        self,
        pulse_name: str,
        amplitude_scale: Optional[Union[ScalarFloat, Sequence[ScalarFloat]]] = None,
        duration: ScalarInt = None,
        condition: ScalarBool = None,
        chirp: ChirpType = None,
        truncate: ScalarInt = None,
        timestamp_stream: StreamType = None,
        continue_chirp: bool = False,
        target: str = "",
        validate: bool = True): 

        return self.physical_channel.play(
            pulse_name = pulse_name,
            amplitude_scale = amplitude_scale,
            duration = duration,
            condition = condition,
            chirp = chirp,
            truncate = truncate,
            timestamp_stream = timestamp_stream,
            continue_chirp = continue_chirp,
            target = target,
            validate = validate,
        )