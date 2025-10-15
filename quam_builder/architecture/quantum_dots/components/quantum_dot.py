from quam.core import quam_dataclass, QuamComponent
from voltage_gate import VoltageGate
from quam.components import Channel
from typing import Dict

__all__ = ["QuantumDot"]


@quam_dataclass
class QuantumDot:
    """
    Quam component for a single Quantum Dot
    """
    id: str
    physical_channel: Channel
    sticky_tracker: float = 0.0

    def go_to_voltage(self, voltage) -> Dict[str, float]:
        """
        Returns a dict entry to be handled by the QPU, input directly into the VirtualGateSet
        """
        self.sticky_tracker = voltage
        return {self.id: voltage}
