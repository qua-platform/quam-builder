from typing import Union, TYPE_CHECKING

from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.components.mixin import VoltagePointMacroMixin

from quam_builder.tools.voltage_sequence import VoltageSequence

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["QPU"]


@quam_dataclass
class QPU(VoltagePointMacroMixin):
    """
    Quam component for the QPU

    The macros dictionary is inherited from VoltagePointMacroMixin and can be used
    to store parameterized macros that are called at programming time.
    """
    id: Union[int, str] = 'QPU'

    @property
    def name(self) -> str:
        """Return the name of the QPU (required by QuantumComponent)"""
        return str(self.id)

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

    # Voltage and point methods (go_to_voltages, step_to_voltages, ramp_to_voltages,
    # add_point, step_to_point, ramp_to_point) are now provided by VoltagePointMacroMixin

    def get_offset(self):
        v = getattr(self.physical_channel, "offset_parameter", None)
        return float(v()) if callable(v) else 0.0