from typing import Dict, TYPE_CHECKING

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.tools.voltage_sequence import VoltageSequence
if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["BarrierGate"]


@quam_dataclass
class BarrierGate(VoltageGate):
    """
    A class for a BarrierGate channel
    """
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

    def step_to_voltages(self, voltage: float, duration:int = 16) -> Dict[str, float]:
        """
        Applies self.voltage_sequence.step_to_voltages({self.id: voltage})

        The VoltageSequence forms part of the VirtualGateSet, and so feeding the votlage_sequence the name of the 
        BarrierGate id (internally == the VirtualGateSet axis name), should internally resolve this dictionary. 

        Arbitrary duration, since elements should be sticky
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
        BarrierGate id (internally == the VirtualGateSet axis name), should internally resolve this dictionary. 
        """
        if self.voltage_sequence is None: 
            raise RuntimeError(f"QuantumDot {self.id} has no VoltageSequence. Ensure that the VoltageSequence is mapped to the" + 
                               " relevant QUAM voltage_sequence.")
        self.current_voltage = voltage
        return self.voltage_sequence.ramp_to_voltages({self.id: voltage}, ramp_duration = ramp_duration, duration = duration)
