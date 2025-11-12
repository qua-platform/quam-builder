import numpy as np
from typing import Dict, Union, Tuple, Optional, List, Sequence, TYPE_CHECKING

from quam.core import quam_dataclass, QuamComponent
from quam.components import Channel
from quam_builder.architecture.quantum_dots.components.macros import VoltagePointMacroMixin
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
class QuantumDot(QuamComponent, VoltagePointMacroMixin):
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

    def _update_current_voltage(self, voltage: float):
        """Update the tracked current voltage."""
        self.current_voltage = voltage

    # Voltage and point methods (go_to_voltages, step_to_voltages, ramp_to_voltages,
    # add_point, step_to_point, ramp_to_point) are now provided by VoltagePointMacroMixin

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