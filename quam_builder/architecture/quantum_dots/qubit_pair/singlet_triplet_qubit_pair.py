# Quantum component inheritance depth is framework-driven for QuAM dataclasses.
# pylint: disable=too-many-ancestors

from typing import Any, Dict, Optional, Union, TYPE_CHECKING
from dataclasses import field
from qm.qua import wait

from quam.core import quam_dataclass
from quam.components import QubitPair

from quam_builder.architecture.quantum_dots.components import VoltageGate, XYDriveBase
from quam_builder.architecture.quantum_dots.components.mixins import VoltageMacroMixin
from quam_builder.architecture.quantum_dots.qubit import SingletTripletQubit

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["SingletTripletQubitPair"]


@quam_dataclass
class SingletTripletQubitPair(VoltageMacroMixin, QubitPair):
    """
    Class representing a Singlet Triplet Qubit Pair.

    Attributes:
        qubit_control (LDQubit): The first Singlet Triplet Qubit instance
        qubit_target (LDQubit): The second Singlet Triplet Qubit instance
        gate_fidelity (Dict[str, Any]): Collection of two-qubit gate fidelity metrics.
        points (Dict[str, Dict[str, float]]): A dictionary of instantiated macro points.

    Methods:
        step_to_point: Steps to a pre-defined point in the internal points dict.
        ramp_to_point: Ramps to a pre-defined point in the internal points dict.
    """

    id: Union[str, int]

    qubit_control: SingletTripletQubit
    qubit_target: SingletTripletQubit

    gate_fidelity: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        if self.id is None:
            self.id = f"{self.qubit_control.name}_{self.qubit_target.name}"

    @property
    def voltage_sequence(self):
        return self.qubit_control.voltage_sequence

    @property
    def machine(self) -> "BaseQuamQD":
        return self.qubit_control.machine

    def _get_component_id_for_voltages(self) -> str:
        """
        Override to use the detuning axis for voltage operations on the qubit pair.

        Returns:
            str: The detuning axis name to use for voltage operations
        """
        return None
