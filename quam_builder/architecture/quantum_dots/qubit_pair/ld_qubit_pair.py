# Quantum component inheritance depth is framework-driven for QuAM dataclasses.
# pylint: disable=too-many-ancestors

from typing import Any, Dict, Optional, Union, TYPE_CHECKING
from dataclasses import field
from qm.qua import wait

from quam.core import quam_dataclass
from quam.components import QubitPair

from quam_builder.architecture.quantum_dots.components import (
    QuantumDotPair,
)
from quam_builder.architecture.quantum_dots.components import VoltageGate, XYDriveBase
from quam_builder.architecture.quantum_dots.components.mixins import VoltageMacroMixin
from quam_builder.architecture.quantum_dots.qubit import LDQubit

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["LDQubitPair"]


@quam_dataclass
class LDQubitPair(VoltageMacroMixin, QubitPair):
    """
    Class representing a Loss-DiVincenzo Qubit Pair.
    Internally, a QuantumDotPair will be instantiated.

    Attributes:
        qubit_control (LDQubit): The first Loss-DiVincenzo Qubit instance
        qubit_target (LDQubit): The second Loss-DiVincenzo Qubit instance
        gate_fidelity (Dict[str, Any]): Collection of two-qubit gate fidelity metrics.
        points (Dict[str, Dict[str, float]]): A dictionary of instantiated macro points.

    Methods:
        add_quantum_dot_pair: Adds the QuantumDotPair associated with the Qubit instances.
        add_point: Adds a named voltage point to the associated VirtualGateSet. Can accept qubit names
        step_to_point: Steps to a pre-defined point in the internal points dict.
        ramp_to_point: Ramps to a pre-defined point in the internal points dict.
    """

    id: Union[str, int]

    qubit_control: LDQubit
    qubit_target: LDQubit

    quantum_dot_pair: QuantumDotPair = None
    gate_fidelity: Dict[str, Any] = field(default_factory=dict)

    xy: XYDriveBase = None
    heralded_initialize_target_state: Optional[int] = None

    def __post_init__(self):
        super().__post_init__()
        if self.id is None:
            self.id = f"{self.qubit_control.name}_{self.qubit_target.name}"

    @property
    def physical_channel(self) -> VoltageGate:
        return self.quantum_dot_pair.physical_channel

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

    def _create_point_name(self, point_name: str) -> str:
        """Delegate point naming to the quantum_dot_pair so keys match the gate set."""
        return self.quantum_dot_pair._create_point_name(point_name)

    def idle(self, duration) -> None:
        wait(
            duration,
            self.physical_channel.name,
            self.qubit_target.physical_channel.name,
            self.qubit_target.xy.name,
            self.qubit_control.physical_channel.name,
            self.qubit_control.xy.name,

        )
