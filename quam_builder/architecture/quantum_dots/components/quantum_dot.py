from quam.core import quam_dataclass, QuamComponent
from quam.components import Channel
from typing import Dict, Union, Tuple, Optional, List, Sequence
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

__all__ = ["QuantumDot"]


@quam_dataclass
class QuantumDot(QuamComponent):
    """
    Quam component for a single Quantum Dot
    Attributes: 
        id (str): The id of the QuantumDot
        physical_channel (VoltageGate): The VoltageGate instance directly coupled to the QuantumDot
        current_voltage (float): The current voltage offset of the QuantumDot via the OPX. Default is zero. 
        charge_number (int): The integer number of charges currently on the QuantumDot

    Methods: 
        go_to_voltage: Returns a dict entry to be used via VirtualGateSet. 
        get_offset: Returns the current value of the external voltage source. 
        set_offset: Sets the external voltage source to the new value.
    """
    id: Union[int, str]
    physical_channel: VoltageGate
    voltage_sequence: VoltageSequence = None
    current_voltage: float = 0.0
    charge_number: int = 0

    @property
    def name(self) -> str: 
        return self.id if isinstance(self.id, str) else f"dot{self.id}"

    def step_to_voltages(self, voltage: float, duration:int = 16) -> Dict[str, float]:
        """
        Applies self.voltage_sequence.step_to_voltages({self.id: voltage})

        The VoltageSequence forms part of the VirtualGateSet, and so feeding the votlage_sequence the name of the 
        QuantumDot id (internally == the VirtualGateSet axis name), should internally resolve this dictionary. 
        """
        if self.voltage_sequence is None: 
            raise RuntimeError(f"QuantumDot {self.id} has no VoltageSequence. Ensure that the VoltageSequence is mapped to the" + 
                               " relevant QUAM voltage_sequence.")
        self.current_voltage = voltage
        return self.voltage_sequence.step_to_voltages({self.id: voltage}, duration = duration)
    
    def ramp_to_voltages(self, voltage: float, ramp_duration: int, duration:int = 16) -> Dict[str, float]:
        """
        Applies self.voltage_sequence.ramp_to_voltages({self.id: voltage}, ramp_duration = ramp_duration)

        The VoltageSequence forms part of the VirtualGateSet, and so feeding the votlage_sequence the name of the 
        QuantumDot id (internally == the VirtualGateSet axis name), should internally resolve this dictionary. 
        """
        if self.voltage_sequence is None: 
            raise RuntimeError(f"QuantumDot {self.id} has no VoltageSequence. Ensure that the VoltageSequence is mapped to the" + 
                               " relevant QUAM voltage_sequence.")
        self.current_voltage = voltage
        return self.voltage_sequence.ramp_to_voltages({self.id: voltage}, ramp_duration = ramp_duration, duration = duration)
    
    def get_offset(self): 
        v = getattr(self.physical_channel, "offset_parameter", None)
        return float(v()) if callable(v) else 0.0
    
    def set_offset(self, value: float): 
        if self.physical_channel.offset_parameter is not None: 
            self.physical_channel.offset_parameter(value)
            return 
        raise ValueError("External offset source not connected")


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