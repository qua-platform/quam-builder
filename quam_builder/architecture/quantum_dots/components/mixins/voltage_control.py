"""Base voltage control mixin for quantum dot components.

This module provides the foundational voltage control operations that all
quantum dot components share.
"""

from abc import abstractmethod
from typing import TYPE_CHECKING, Dict

from quam.core import quam_dataclass
from quam.components import QuantumComponent

from quam_builder.tools.qua_tools import DurationType, VoltageLevelType

if TYPE_CHECKING:
    from quam_builder.tools.voltage_sequence import VoltageSequence
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["VoltageControlMixin"]


@quam_dataclass
class VoltageControlMixin(QuantumComponent):
    """Base mixin providing fundamental voltage control operations.

    This mixin defines the core voltage control interface that all quantum dot
    components use. It provides:
    - Abstract `voltage_sequence` property that subclasses must implement
    - Machine property to access the root QPU
    - Validation of component IDs against the gate set
    - Basic voltage transition methods (go_to, step_to, ramp_to)

    Classes using this mixin must provide:
        - voltage_sequence: Property returning the VoltageSequence instance
        - id: Attribute identifying the component
    """

    # Attributes that must be provided by the class using the mixin
    id: str

    @property
    def machine(self) -> "BaseQuamQD":
        """Get the root machine instance by traversing up the parent hierarchy.

        This property climbs up the parent ladder to find the top-level machine
        object (BaseQuamQD instance) that contains this component.

        Returns:
            BaseQuamQD: The root machine instance
        """
        obj = self
        while obj.parent is not None:
            obj = obj.parent
        machine = obj
        return machine

    @property
    @abstractmethod
    def voltage_sequence(self) -> "VoltageSequence":
        """Return the VoltageSequence instance. Must be implemented by subclass."""
        ...

    def _validate_component_id_in_gate_set(self, component_id: str) -> None:
        """Validate that the component_id exists in the voltage sequence's gate set.

        For pairs (QuantumDotPair, LDQubitPair), this checks if the detuning axis
        has been defined before voltage operations are attempted.

        Args:
            component_id: The gate/component id to validate

        Raises:
            ValueError: If the component_id is not found in the gate set
        """
        gate_set = self.voltage_sequence.gate_set
        valid_channel_names = gate_set.valid_channel_names

        if component_id not in valid_channel_names:
            component_name = self.__class__.__name__

            raise ValueError(
                f"{component_name} {self.id}: Component id '{component_id}' not found in gate set. "
                f"Valid channel names: {list(valid_channel_names)}"
            )

    def go_to_voltages(self, voltages: Dict[str, VoltageLevelType], duration: DurationType) -> None:
        """Agnostic function to set voltage in a sequence.simultaneous block.

        Whether it is a step or a ramp should be determined by the context manager.
        This method is intended for use within a simultaneous block.

        Args:
            voltages: Target voltages (key: gate/qubit name, value: voltage)
            duration: Duration to hold the voltage in nanoseconds
        """
        self.voltage_sequence.step_to_voltages(voltages, duration=duration)

    def step_to_voltages(
        self, voltages: Dict[str, VoltageLevelType], duration: DurationType
    ) -> None:
        """Step to a specified voltage.

        Args:
            voltages: Target voltages (key: gate/qubit name, value: voltage)
            duration: Duration to hold the voltage in nanoseconds
        """
        self.voltage_sequence.step_to_voltages(voltages, duration=duration)

    def ramp_to_voltages(
        self,
        voltages: Dict[str, VoltageLevelType],
        duration: DurationType,
        ramp_duration: DurationType,
    ) -> None:
        """Ramp to a specified voltage.

        Args:
            voltages: Target voltages (key: gate/qubit name, value: voltage)
            ramp_duration: Duration of the ramp in nanoseconds
            duration: Duration to hold the final voltage in nanoseconds
        """
        self.voltage_sequence.ramp_to_voltages(voltages, duration, ramp_duration)
