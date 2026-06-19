"""Global gate component for quantum dots."""

from typing import Dict, TYPE_CHECKING

from quam.core import quam_dataclass

from .voltage_gate import VoltageGate
from .mixin import VoltageMacroMixin
from quam_builder.tools.voltage_sequence import VoltageSequence

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["GlobalGate"]


@quam_dataclass
class GlobalGate(VoltageMacroMixin):
    """
    A class for a GlobalGate channel
    """

    id: str
    physical_channel: VoltageGate
    current_voltage: float = 0.0

    @property
    def name(self) -> str:
        """Return the name of the global gate (same as id)."""
        return self.id

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

    # Voltage methods (go_to_voltages, step_to_voltages, ramp_to_voltages) are now provided by VoltageMacroMixin
