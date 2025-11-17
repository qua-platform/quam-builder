"""
Mixin classes for voltage point macro functionality.

This module provides mixin classes that implement common voltage point macro methods
to reduce code duplication across quantum dot components.
"""

from typing import Dict, TYPE_CHECKING, Optional, List
from dataclasses import field

from quam.core import quam_dataclass, QuamComponent

if TYPE_CHECKING:
    from quam_builder.tools.voltage_sequence import VoltageSequence
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = ["VoltagePointMacroMixin", "SequenceMacro"]


@quam_dataclass
class SequenceMacro(QuamComponent):
    """
    A callable macro for executing voltage point operations in sequences.

    SequenceMacro encapsulates the parameters needed to perform a voltage operation
    (ramp or step) to a pre-defined voltage point. It can be stored in sequences and
    called later to execute the voltage operation on a quantum dot component.

    Attributes:
        macro_type: Type of macro operation ('ramp' or 'step')
        point_name: Name of the voltage point to target
        duration: Duration to hold the final voltage in nanoseconds (default: 16)
        ramp_duration: Duration of the ramp in nanoseconds, used only for 'ramp' type (default: 16)

    Example:
        >>> # Create a macro for ramping to a point
        >>> macro = SequenceMacro(
        ...     macro_type='ramp',
        ...     point_name='loading_point',
        ...     duration=100,
        ...     ramp_duration=500
        ... )
        >>> # Execute the macro on a quantum dot
        >>> macro(quantum_dot)
    """

    macro_type: str
    point_name: str
    duration: Optional[int] = 16
    ramp_duration: Optional[int] = 16

    # Mapping of macro types to their corresponding method names
    MACRO_TYPE_TO_METHOD = {
        "ramp": "ramp_to_point",
        "step": "step_to_point",
    }

    def __call__(
        self,
        obj,
        macro_type: str = None,
        duration: int = None,
        ramp_duration: int = None,
    ):
        """
        Execute the voltage macro operation on a quantum dot component.

        This method allows the SequenceMacro to be called as a function, executing
        the stored voltage operation on the provided object. Parameters can be
        overridden at call time if needed.

        Args:
            obj: The quantum dot component to execute the macro on (must have
                ramp_to_point or step_to_point methods)
            macro_type: Optional override for the macro type ('ramp' or 'step')
            duration: Optional override for the duration to hold the final voltage (ns)
            ramp_duration: Optional override for the ramp duration (ns), used only for 'ramp' type

        Raises:
            NotImplementedError: If the macro_type is not 'ramp' or 'step'

        Example:
            >>> macro = SequenceMacro(macro_type='ramp', point_name='point1', duration=100)
            >>> macro(quantum_dot)  # Execute with stored parameters
            >>> macro(quantum_dot, duration=200)  # Override duration at call time
        """
        # Allow runtime parameter overrides
        if macro_type is not None:
            self.macro_type = macro_type
        if duration is not None:
            self.duration = duration
        if ramp_duration is not None:
            self.ramp_duration = ramp_duration

        # Validate macro_type before accessing dictionary
        if self.macro_type not in self.MACRO_TYPE_TO_METHOD:
            raise NotImplementedError(
                f"Type {self.macro_type} not implemented. "
                f"Supported types: {list(self.MACRO_TYPE_TO_METHOD.keys())}"
            )

        # Get the appropriate method from the object
        fn = getattr(obj, self.MACRO_TYPE_TO_METHOD[self.macro_type])

        # Execute the appropriate macro type
        if self.macro_type == "ramp":
            fn(
                self.point_name,
                self.ramp_duration,
                duration=self.duration,
            )
        elif self.macro_type == "step":
            fn(
                self.point_name,
                self.duration,
            )

@quam_dataclass
class VoltagePointMacroMixin:
    """
    Mixin class providing voltage point macro methods for quantum dot components.

    This mixin consolidates common voltage control methods to reduce code duplication
    across BarrierGate, QuantumDot, QuantumDotPair, LDQubit, and LDQubitPair classes.

    Classes using this mixin must provide:
        - voltage_sequence: Property returning the VoltageSequence instance
        - id: Attribute identifying the component (used for naming points)

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

    # Attributes that must be provided by the class using the mixin
    id: str
    points: Dict[str, Dict[str, float]] = field(default_factory=dict)
    sequences: Dict[str, List[SequenceMacro]] = field(default_factory=dict)

    @property
    def machine(self) -> "BaseQuamQD":
        """
        Get the root machine instance by traversing up the parent hierarchy.

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

    def _validate_component_id_in_gate_set(self, component_id: str) -> None:
        """
        Validate that the component_id exists in the voltage sequence's gate set.

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

    def _go_to_voltages(self, voltage: float) -> Dict[str, float]:
        """
        Prepare a voltage dictionary for the component.

        This helper method validates the voltage sequence and component ID,
        optionally updates current voltage tracking, and returns a voltage
        dictionary ready for use with voltage sequence methods.

        Args:
            voltage: Target voltage in volts

        Returns:
            Dictionary mapping component ID to voltage value

        Raises:
            RuntimeError: If voltage_sequence is not available
            ValueError: If the component ID is not found in the gate set
        """
        self._validate_voltage_sequence()
        component_id = self._get_component_id_for_voltages()
        self._validate_component_id_in_gate_set(component_id)

        # Allow subclasses to track current voltage if needed
        if hasattr(self, "_update_current_voltage"):
            self._update_current_voltage(voltage)
        return {component_id: voltage}

    def go_to_voltages(self, voltage: float, duration: int = 16) -> None:
        """
        Agnostic function to set voltage in a sequence.simultaneous block.

        Whether it is a step or a ramp should be determined by the context manager.
        This method is intended for use within a simultaneous block.

        Args:
            voltage: Target voltage in volts
            duration: Duration to hold the voltage in nanoseconds (default: 16)
        """

        target_voltages = self._go_to_voltages(voltage)
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
        target_voltages = self._go_to_voltages(voltage)

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
        target_voltages = self._go_to_voltages(voltage)

        return self.voltage_sequence.ramp_to_voltages(
            target_voltages, ramp_duration=ramp_duration, duration=duration
        )

    # ========================================================================
    # Point Macro Methods
    # ========================================================================

    def add_sequence(
        self,
        name: str,
        macro_types: List[str],
        voltages: List[Dict[str, float]],
        durations: List[int],
        ramp_durations: Optional[List[int]] = None,
    ):
        """
        Create a sequence of voltage macros with multiple points.

        This convenience method creates a named sequence by adding multiple voltage
        points and their corresponding macros. Each point is automatically named as
        '{name}_macro_{i}' where i is the index in the list.

        Args:
            name: Name of the sequence to create
            macro_types: List of macro types ('ramp' or 'step') for each point
            voltages: List of voltage dictionaries, one for each point
            durations: List of hold durations (ns) for each point
            ramp_durations: Optional list of ramp durations (ns) for ramp-type macros.
                If None, defaults to [None] for all points.

        Raises:
            AssertionError: If the lengths of the input lists don't match

        Example:
            >>> qd.add_sequence(
            ...     name='loading_sequence',
            ...     macro_types=['ramp', 'step', 'ramp'],
            ...     voltages=[{...}, {...}, {...}],
            ...     durations=[100, 200, 100],
            ...     ramp_durations=[500, None, 300]
            ... )
        """
        if ramp_durations is None:
            ramp_durations = [None] * len(macro_types)

        assert (
            len(durations) == len(ramp_durations) == len(voltages) == len(macro_types)
        ), "All input lists must have the same length"

        for i, (macro_type, duration, ramp_duration, voltage) in enumerate(
            zip(macro_types, durations, ramp_durations, voltages)
        ):
            self.add_point_to_sequence(
                sequence_name=name,
                point_name=f"{name}_macro_{i}",
                macro_type=macro_type,
                duration=duration,
                ramp_duration=ramp_duration,
                voltages=voltage,
            )

    def add_point_to_sequence(
        self,
        sequence_name: str,
        point_name: str,
        macro_type: str,
        duration: int,
        ramp_duration: Optional[int] = None,
        voltages: Optional[Dict[str, float]] = None,
    ):
        """
        Add a single voltage point and macro to a named sequence.

        This method adds a voltage point to the gate set (if voltages are provided)
        and appends a corresponding SequenceMacro to the named sequence. If the
        sequence doesn't exist yet, it will be created.

        Args:
            sequence_name: Name of the sequence to add the point to
            point_name: Name of the voltage point
            macro_type: Type of macro operation ('ramp' or 'step')
            duration: Duration to hold the final voltage in nanoseconds
            ramp_duration: Duration of the ramp in nanoseconds (for 'ramp' type).
                Defaults to 16 if None.
            voltages: Optional voltage dictionary for the point. If provided,
                the point will be added/updated in the gate set.

        Example:
            >>> qd.add_point_to_sequence(
            ...     sequence_name='my_sequence',
            ...     point_name='point1',
            ...     macro_type='ramp',
            ...     duration=100,
            ...     ramp_duration=500,
            ...     voltages={'virtual_dot_1': 0.5}
            ... )
        """
        if voltages is not None:
            self.add_point(
                point_name=point_name,
                voltages=voltages,
                replace_existing_point=True,
            )

        if sequence_name not in self.sequences:
            self.sequences[sequence_name] = []

        self.sequences[sequence_name].append(
            SequenceMacro(
                macro_type=macro_type,
                point_name=point_name,
                duration=duration,
                ramp_duration=ramp_duration if ramp_duration is not None else 16,
            )
        )

    def run_sequence(self, name: str):
        """
        Execute all macros in a named sequence.

        This method iterates through all SequenceMacros in the specified sequence
        and executes them in order on the current component.

        Args:
            name: Name of the sequence to execute

        Raises:
            KeyError: If the sequence name doesn't exist

        Example:
            >>> # First create a sequence
            >>> qd.add_sequence(...)
            >>> # Then execute it
            >>> with qua.program() as prog:
            ...     qd.run_sequence('my_sequence')
        """
        for fn in self.sequences[name]:
            fn(self)

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

    def _validate_point_name(self, point_name: str) -> str:
        """
        Validate that a point name exists and return its full name in the gate set.

        Args:
            point_name: The point name to validate (without prefix)

        Returns:
            The full point name in the gate set (with prefix)

        Raises:
            ValueError: If the point name has not been registered with add_point
        """
        if point_name not in self.points:
            component_type = self.__class__.__name__
            name_prefix = self._get_point_name_prefix()
            raise ValueError(
                f"Point {point_name} not in registered points for {component_type} {name_prefix}: "
                f"{list(self.points.keys())}"
            )

        name_in_sequence = f"{self._get_point_name_prefix()}_{point_name}"

        return name_in_sequence

    def step_to_point(self, point_name: str, duration: int = 16) -> None:
        """
        Step to a pre-defined voltage point.

        Args:
            point_name: Name of the point to step to (must be previously added with add_point)
            duration: Duration to hold the point in nanoseconds (default: 16)

        Raises:
            ValueError: If the point has not been registered
        """
        name_in_sequence = self._validate_point_name(point_name)
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

        name_in_sequence = self._validate_point_name(point_name)
        return self.voltage_sequence.ramp_to_point(
            name=name_in_sequence, duration=duration, ramp_duration=ramp_duration
        )
