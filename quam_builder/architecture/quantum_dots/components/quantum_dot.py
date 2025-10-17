from quam.core import quam_dataclass, QuamComponent
from quam.components import Channel
from typing import Dict, Union, Tuple, Optional


from qm import QuantumMachine

from quam_builder.architecture.quantum_dots.components import VoltageGate

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
    current_voltage: float = 0.0
    charge_number: int = 0

    @property
    def name(self) -> str: 
        return self.id if isinstance(self.id, str) else f"dot{self.id}"

    def go_to_voltage(self, voltage: float) -> Dict[str, float]:
        """
        Returns a dict entry to be handled by the QPU, input directly into the VirtualGateSet
        """
        self.current_voltage = voltage
        return {self.id: voltage}
    
    @property
    def get_offset(self): 
        if self.physical_channel.offset_parameter is not None: 
            return self.physical_channel.offset_parameter()
        return 0.0
    
    def set_offset(self, value: float): 
        if self.physical_channel.offset_parameter is not None: 
            self.physical_channel.offset_parameter(value)
        raise ValueError("External offset source not connected")
