from typing import Dict

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.tools.voltage_sequence import VoltageSequence


__all__ = ["BarrierGate"]


@quam_dataclass
class BarrierGate(VoltageGate):
    """
    A class for a BarrierGate channel
    """
    voltage_sequence: VoltageSequence

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
