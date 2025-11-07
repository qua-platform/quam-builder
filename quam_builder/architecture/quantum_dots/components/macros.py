"""
Mixin classes for voltage point macro functionality.

This module provides mixin classes that implement common voltage point macro methods
to reduce code duplication across quantum dot components.
"""

from typing import Dict, TYPE_CHECKING
from dataclasses import field

if TYPE_CHECKING:
    from quam_builder.tools.voltage_sequence import VoltageSequence
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["VoltagePointMacroMixin"]


class VoltagePointMacroMixin:
    """
    Mixin class providing voltage point macro methods for quantum dot components.

    This mixin consolidates common voltage control methods to reduce code duplication
    across BarrierGate, QuantumDot, QuantumDotPair, LDQubit, and LDQubitPair classes.

    Classes using this mixin must provide:
        - voltage_sequence: Property returning the VoltageSequence instance
        - id: Attribute identifying the component (used for naming points)
        - points: Dict attribute to store point definitions (Dict[str, Dict[str, float]])

    Optional attributes/methods for customization:
        - _get_point_name_prefix(): Method to customize the prefix for point names
          (defaults to self.id or self.name if available)
        - _should_map_qubit_names(): Method returning True to enable qubit name mapping
          (defaults to False)
        - machine: Property required if qubit name mapping is enabled
        - _update_current_voltage(): Method called after voltage operations to update
          current voltage tracking (if needed)

    Example usage:
        @quam_dataclass
        class MyComponent(QuamComponent, VoltagePointMacroMixin):
            id: str
            physical_channel: VoltageGate
            points: Dict[str, Dict[str, float]] = field(default_factory=dict)

            @property
            def voltage_sequence(self) -> VoltageSequence:
                # Implementation to return voltage sequence
                ...
    """

    # This will be provided by the class using the mixin
    id: str
    points: Dict[str, Dict[str, float]]

    @property
    def voltage_sequence(self) -> "VoltageSequence":
        """Return the VoltageSequence instance. Must be implemented by subclass."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement voltage_sequence property"
        )

    def _get_point_name_prefix(self) -> str:
        """
        Get the prefix to use for point names in the gate set.

        By default, uses self.name if available, otherwise self.id.
        Override this method to customize the naming scheme.

        Returns:
            str: The prefix to use for point names
        """
        # Prefer 'name' attribute if it exists (for LDQubit), otherwise use 'id'
        return getattr(self, "name", self.id)

    def _should_map_qubit_names(self) -> bool:
        """
        Whether to map qubit names to quantum dot ids in voltage dictionaries.

        By default, returns False. Override to return True for classes that should
        perform qubit name mapping (e.g., LDQubit, LDQubitPair).

        Returns:
            bool: True if qubit name mapping should be performed
        """
        return False

    def _get_component_id_for_voltages(self) -> str:
        """
        Get the id to use when building voltage dictionaries.

        By default, returns self.id. For LDQubit, this should return self.quantum_dot.id
        since voltage operations target the quantum dot, not the qubit itself.

        Returns:
            str: The id to use in voltage dictionaries
        """
        return self.id

    def _validate_voltage_sequence(self) -> None:
        """Validate that voltage_sequence is available."""
        if self.voltage_sequence is None:
            component_name = self.__class__.__name__
            component_id = self._get_point_name_prefix()
            raise RuntimeError(
                f"{component_name} {component_id} has no VoltageSequence. "
                "Ensure that the VoltageSequence is mapped to the relevant QUAM voltage_sequence."
            )

    def _process_voltages_for_gate_set(
        self, voltages: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Process voltages dictionary, optionally mapping qubit names to quantum dot ids.

        Args:
            voltages: Dictionary mapping gate/qubit names to voltages

        Returns:
            Processed voltages dictionary with qubit names mapped to quantum dot ids
            (if mapping is enabled)
        """
        if not self._should_map_qubit_names():
            return voltages

        # Perform qubit name mapping
        processed_voltages = {}
        machine: "BaseQuamQD" = self.machine
        qubit_mapping = machine.qubits

        for gate_name, voltage in voltages.items():
            # If gate_name is a qubit name, map it to the quantum dot id
            if gate_name in qubit_mapping:
                gate_name = qubit_mapping[gate_name].id
            processed_voltages[gate_name] = voltage

        return processed_voltages

    # ========================================================================
    # Direct Voltage Methods
    # ========================================================================

    def go_to_voltages(self, voltage: float, duration: int = 16) -> None:
        """
        Agnostic function to set voltage in a sequence.simultaneous block.

        Whether it is a step or a ramp should be determined by the context manager.
        This method is intended for use within a simultaneous block.

        Args:
            voltage: Target voltage in volts
            duration: Duration to hold the voltage in nanoseconds (default: 16)
        """
        self._validate_voltage_sequence()
        component_id = self._get_component_id_for_voltages()
        target_voltages = {component_id: voltage}
        return self.voltage_sequence.step_to_voltages(
            target_voltages, duration=duration
        )

    def step_to_voltages(self, voltage: float, duration: int = 16) -> None:
        """
        Step to a specified voltage.

        Args:
            voltage: Target voltage in volts
            duration: Duration to hold the voltage in nanoseconds (default: 16)
        """
        self._validate_voltage_sequence()
        component_id = self._get_component_id_for_voltages()
        target_voltages = {component_id: voltage}

        # Allow subclasses to track current voltage if needed
        if hasattr(self, "_update_current_voltage"):
            self._update_current_voltage(voltage)

        return self.voltage_sequence.step_to_voltages(
            target_voltages, duration=duration
        )

    def ramp_to_voltages(
        self, voltage: float, ramp_duration: int, duration: int = 16
    ) -> None:
        """
        Ramp to a specified voltage.

        Args:
            voltage: Target voltage in volts
            ramp_duration: Duration of the ramp in nanoseconds
            duration: Duration to hold the final voltage in nanoseconds (default: 16)
        """
        self._validate_voltage_sequence()
        component_id = self._get_component_id_for_voltages()
        target_voltages = {component_id: voltage}

        # Allow subclasses to track current voltage if needed
        if hasattr(self, "_update_current_voltage"):
            self._update_current_voltage(voltage)

        return self.voltage_sequence.ramp_to_voltages(
            target_voltages, ramp_duration=ramp_duration, duration=duration
        )

    # ========================================================================
    # Point Macro Methods
    # ========================================================================

    def add_point(
        self,
        point_name: str,
        voltages: Dict[str, float],
        duration: int = 16,
        replace_existing_point: bool = False,
    ) -> None:
        """
        Add a voltage point macro to the associated VirtualGateSet.

        Args:
            point_name: The name of the point in the VirtualGateSet
            voltages: A dictionary of the associated voltages. For LDQubit and
                LDQubitPair, this can include qubit names which will be automatically
                mapped to quantum dot names.
            duration: The duration to hold the point in nanoseconds (default: 16)
            replace_existing_point: If True, replace an existing point with the same
                name. If False, raise an error if the point already exists (default: False)

        Raises:
            ValueError: If the point already exists and replace_existing_point is False
        """
        gate_set = self.voltage_sequence.gate_set
        existing_points = gate_set.get_macros()

        # Get the prefix for the point name
        name_prefix = self._get_point_name_prefix()
        name_in_sequence = f"{name_prefix}_{point_name}"

        # Check if point already exists
        if name_in_sequence in existing_points and not replace_existing_point:
            component_type = self.__class__.__name__
            raise ValueError(
                f"Point name {point_name} already exists for {component_type} {name_prefix}. "
                "If you would like to replace, please set replace_existing_point = True"
            )

        # Store original voltages in points dict
        self.points[point_name] = voltages

        # Process voltages (with optional qubit name mapping)
        processed_voltages = self._process_voltages_for_gate_set(voltages)

        # Add point to gate set
        gate_set.add_point(
            name=name_in_sequence, voltages=processed_voltages, duration=duration
        )

    def step_to_point(self, point_name: str, duration: int = 16) -> None:
        """
        Step to a pre-defined voltage point.

        Args:
            point_name: Name of the point to step to (must be previously added with add_point)
            duration: Duration to hold the point in nanoseconds (default: 16)

        Raises:
            ValueError: If the point has not been registered
        """
        if point_name not in self.points:
            component_type = self.__class__.__name__
            name_prefix = self._get_point_name_prefix()
            raise ValueError(
                f"Point {point_name} not in registered points for {component_type} {name_prefix}: "
                f"{list(self.points.keys())}"
            )

        name_in_sequence = f"{self._get_point_name_prefix()}_{point_name}"
        return self.voltage_sequence.step_to_point(
            name=name_in_sequence, duration=duration
        )

    def ramp_to_point(
        self, point_name: str, ramp_duration: int, duration: int = 16
    ) -> None:
        """
        Ramp to a pre-defined voltage point.

        Args:
            point_name: Name of the point to ramp to (must be previously added with add_point)
            ramp_duration: Duration of the ramp in nanoseconds
            duration: Duration to hold the final point in nanoseconds (default: 16)

        Raises:
            ValueError: If the point has not been registered
        """
        if point_name not in self.points:
            component_type = self.__class__.__name__
            name_prefix = self._get_point_name_prefix()
            raise ValueError(
                f"Point {point_name} not in registered points for {component_type} {name_prefix}: "
                f"{list(self.points.keys())}"
            )

        name_in_sequence = f"{self._get_point_name_prefix()}_{point_name}"
        return self.voltage_sequence.ramp_to_point(
            name=name_in_sequence, duration=duration, ramp_duration=ramp_duration
        )
