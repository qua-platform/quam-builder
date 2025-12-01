from typing import Union, Dict, TYPE_CHECKING

from quam.core import quam_dataclass
from quam.components import QubitPair

from quam_builder.architecture.quantum_dots.components import (
    QuantumDotPair,
)
from quam_builder.architecture.quantum_dots.macros.point_macros import (
    VoltagePointMacroMixin,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["LDQubitPair"]


@quam_dataclass
class LDQubitPair(QubitPair, VoltagePointMacroMixin):
    """
    Class representing a Loss-DiVincenzo Qubit Pair.
    Internally, a QuantumDotPair will be instantiated.

    Attributes:
        qubit_control (LDQubit): The first Loss-DiVincenzo Qubit instance
        qubit_target (LDQubit): The second Loss-DiVincenzo Qubit instance
        points (Dict[str, Dict[str, float]]): A dictionary of instantiated macro points.

    Methods:
        add_quantum_dot_pair: Adds the QuantumDotPair associated with the Qubit instances.
        add_point: Adds a point macro to the associated VirtualGateSet. Also registers said point in the internal points attribute. Can accept qubit names
        step_to_point: Steps to a pre-defined point in the internal points dict.
        ramp_to_point: Ramps to a pre-defined point in the internal points dict.
    """

    id: Union[str, int]

    qubit_control: LDQubit
    qubit_target: LDQubit

    quantum_dot_pair: QuantumDotPair = None

    def __post_init__(self):
        if self.id is None:
            self.id = f"{self.qubit_control.id}_{self.qubit_target.id}"
        self.gate_id = self.quantum_dot_pair.gate_id

    @property
    def detuning_axis_name(self): 
        if self.quantum_dot_pair is None: 
            raise ValueError("No QuantumDotPair in LDQubitPair") 
        return self.quantum_dot_pair.detuning_axis_name
    
    @property
    def voltage_sequence(self): 
        if self.quantum_dot_pair is None: 
            raise ValueError("No QuantumDotPair in LDQubitPair") 
        return self.quantum_dot_pair.voltage_sequence
    
    @property 
    def machine(self) -> "BaseQuamQD":
        return self.quantum_dot_pair.machine

    def _get_component_id_for_voltages(self) -> str:
        """
        Override to use the detuning axis for voltage operations on the qubit pair.

        Returns:
            str: The detuning axis name to use for voltage operations
        """
        return self.detuning_axis_name

    # Voltage point methods (add_point, step_to_point, ramp_to_point) are now provided by VoltagePointMacroMixin
