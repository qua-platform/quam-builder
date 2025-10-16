from quam.core import quam_dataclass, QuamComponent
from quam.components import Channel
from typing import Dict, Union, Tuple, Optional


from qm import QuantumMachine

from quam_builder.architecture.quantum_dots.components import VoltageGate

__all__ = ["QuantumDot"]


@quam_dataclass
class QuantumDot:
    """
    Quam component for a single Quantum Dot
    """
    id: Union[int, str]
    physical_channel: VoltageGate
    current_voltage: float = 0.0


    def go_to_voltage(self, voltage) -> Dict[str, float]:
        """
        Returns a dict entry to be handled by the QPU, input directly into the VirtualGateSet
        """
        self.current_voltage = voltage
        return {self.id: voltage}
    