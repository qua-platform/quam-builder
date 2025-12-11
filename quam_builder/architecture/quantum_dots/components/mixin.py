"""
Mixin classes for voltage point macro functionality.

This module provides mixin classes that implement common voltage point macro methods
to reduce code duplication across quantum dot components.
"""
from quam.core.macro import QuamMacro
from typing import Dict, TYPE_CHECKING, Optional, List, Any
from dataclasses import field
from copy import deepcopy

from quam_builder.architecture.quantum_dots.macros import SequenceMacro, StepPointMacro, RampPointMacro, ConditionalMacro
from quam_builder.architecture.quantum_dots.macros.default_macros import DEFAULT_MACROS
from quam.core import quam_dataclass, QuamComponent
from quam.components import QuantumComponent

from quam_builder.tools.qua_tools import DurationType, VoltageLevelType

from typing import Dict, TYPE_CHECKING
from dataclasses import field

from quam.core import quam_dataclass

if TYPE_CHECKING:
    from quam_builder.tools.voltage_sequence import VoltageSequence
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = [
    "VoltagePointMacroMixin",
]

@quam_dataclass
class VoltagePointMacroMixin(QuantumComponent):
    """
    Mixin class providing voltage point macro methods for quantum dot components.

    This mixin consolidates common voltage control methods to reduce code duplication
    across BarrierGate, QuantumDot, QuantumDotPair, LDQubit, and LDQubitPair classes.

    Classes using this mixin must provide:
        - voltage_sequence: Property returning the VoltageSequence instance
        - id: Attribute identifying the component (used for naming points)

    Optional attributes/methods for customization:
        - machine: Property required if qubit name mapping is enabled
          current voltage tracking (if needed)

    Features:
        - Dynamic macro access: Macros in self.macros are callable as methods via __getattr__
        - Fluent API: Chain macro definitions with with_step_point(), with_ramp_point(), with_sequence()
        - Serializable: All state stored in self.macros dict, compatible with QuAM serialization

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

        # Define macros during calibration
        component.with_step_point("idle", {"gate": 0.1}, hold_duration=100)
        component.with_ramp_point("load", {"gate": 0.3}, hold_duration=200, ramp_duration=500)
        component.with_sequence("init", ["idle", "load"])

        # Call as methods in QUA program
        with program() as prog:
            component.idle()  # Calls StepPointMacro
            component.load()  # Calls RampPointMacro
            component.init()  # Calls SequenceMacro
    """

    # Attributes that must be provided by the class using the mixin
    id: str
    macros: Dict[str, QuamMacro] = field(default_factory=dict)

    def __post_init__(self):
        # Ensure macro containers exist and set parent links when possible
        if not hasattr(self, "macros") or self.macros is None:
            self.macros = {}

        # Add default macros if not already present
        for macro_name, macro_class in DEFAULT_MACROS.items():
            if macro_name not in self.macros:
                # Use a fresh copy per component to avoid sharing parent links
                self.macros[macro_name] = macro_class()

        # Attach parents for any pre-populated entries
        for macro in self.macros.values():
            if getattr(macro, "parent", None) is None:
                macro.parent = self

    def __getattr__(self, name):
        """
        Enable calling macros as methods via attribute access.

        This allows dynamically-registered macros to be called as if they were
        methods decorated with @QuantumComponent.register_macro, providing a
        cleaner API: component.my_macro() instead of component.macros['my_macro']()

        Serialization-safe: No instance state is modified, macros are resolved
        from self.macros at access time.

        Example:
            component.macros['idle'] = StepPointMacro(...)
            component.idle()  # Calls the macro via __getattr__

        Args:
            name: Attribute name to resolve

        Returns:
            Callable that executes the macro with optional parameter overrides

        Raises:
            AttributeError: If attribute/macro not found
        """
        # First try normal attribute resolution through the descriptor protocol
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            # Check if it's a registered macro
            try:
                macros_dict = object.__getattribute__(self, "__dict__").get(
                    "macros", {}
                )
                if macros_dict and name in macros_dict:
                    # Return a bound method-like callable
                    # Note: apply() uses self.parent internally, no need to pass component
                    def macro_method(**kwargs):
                        return macros_dict[name].apply(**kwargs)

                    macro_method.__name__ = name
                    macro_method.__doc__ = getattr(
                        macros_dict[name], "__doc__", f"Execute {name} macro"
                    )
                    return macro_method
            except (AttributeError, KeyError):
                pass

            # If not found, raise AttributeError with helpful message
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute or macro '{name}'"
            )

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

    def go_to_voltages(
        self, voltages: Dict[str, VoltageLevelType], duration: DurationType
    ) -> None:
        """
        Agnostic function to set voltage in a sequence.simultaneous block.

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
        """
        Step to a specified voltage.

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
        """
        Ramp to a specified voltage.

        Args:
            voltages: Target voltages (key: gate/qubit name, value: voltage)
            ramp_duration: Duration of the ramp in nanoseconds
            duration: Duration to hold the final voltage in nanoseconds
        """
        self.voltage_sequence.ramp_to_voltages(voltages, duration, ramp_duration)

    def add_point(
        self,
        point_name: str,
        voltages: Dict[str, float],
        duration: int = 16,
        replace_existing_point: bool = True,
    ) -> str:
        """
        Define a voltage point in the gate set for later use by macros.

        This method registers a named voltage configuration in the VirtualGateSet
        with a prefixed name: "{component.id}_{point_name}". Once registered,
        the point can be referenced by StepPointMacro and RampPointMacro instances.

        Following quam's Pulse → Macro → Operation pattern:
        - Voltage point ≈ Pulse definition
        - PointMacro ≈ PulseMacro
        - Sequence/Operation ≈ Gate

        Args:
            point_name: Local name for the point (without prefix). Used in macro references.
            voltages: Voltage values for each gate. Key format depends on component type:
                     - QuantumDot: Use gate IDs (e.g., 'virtual_dot_0')
                     - LDQubit/LDQubitPair: Can use qubit names (e.g., 'Q0'), automatically
                       mapped to quantum dot IDs if _should_map_qubit_names() returns True
            duration: Default hold duration for this point (nanoseconds, default: 16).
                     Can be overridden when creating macros or during execution.
            replace_existing_point: If True (default), overwrites existing point with same name.
                                   If False, raises ValueError if point exists.

        Returns:
            str: The full gate_set name ("{component.id}_{point_name}")

        Raises:
            ValueError: If point already exists and replace_existing_point is False

        Example:
            .. code-block:: python

                # Assume quantum_dot is a component with VoltagePointMacroMixin

                # Define voltage points
                quantum_dot.add_point('idle', voltages={'virtual_dot_0': 0.1})
                # Returns: 'quantum_dot_0_idle'

                quantum_dot.add_point('loading', voltages={'virtual_dot_0': 0.3})
                # Returns: 'quantum_dot_0_loading'

                # Create macros referencing these points
                quantum_dot.macros['idle'] = StepPointMacro('idle', hold_duration=100)
                quantum_dot.macros['load'] = RampPointMacro('loading',
                                                             hold_duration=200,
                                                             ramp_duration=500)

                # Execute
                quantum_dot.macros['idle']()
        """
        gate_set = self.voltage_sequence.gate_set
        existing_points = gate_set.get_macros()

        # Construct full gate_set name with component prefix
        full_name = self._create_point_name(point_name)

        # Check if point already exists
        if full_name in existing_points and not replace_existing_point:
            raise ValueError(
                f"Point '{point_name}' already exists as '{full_name}'. "
                "Set replace_existing_point=True to overwrite."
            )

        # Validate voltage keys
        for channel_name in voltages.keys():
            self._validate_component_id_in_gate_set(channel_name)

        # Register in gate set
        gate_set.add_point(name=full_name, voltages=voltages, duration=duration)

        return full_name

    def _create_point_name(self, point_name: str) -> str:
        """
        Construct the full gate_set name from a local point name.

        Args:
            point_name: Local point name (without component prefix)

        Returns:
            str: Full gate_set name in format "{component.id}_{point_name}"
        """
        return f"{self.id}_{point_name}"

    def step_to_point(self, point_name: str, duration: Optional[int] = None) -> None:
        """
        Step instantly to a pre-defined voltage point (convenience method).

        This is a convenience wrapper around voltage_sequence.step_to_point()
        that handles automatic name prefixing. For reusable operations, consider
        creating a StepPointMacro instead and storing it in self.macros.

        Args:
            point_name: Local point name (without prefix, must be added via add_point())
            duration: Hold duration in nanoseconds (default: uses point's default)

        Raises:
            KeyError: If the point has not been registered via add_point()

        Example:
            .. code-block:: python

                # Assume quantum_dot is a component with VoltagePointMacroMixin

                # Direct usage (convenience)
                quantum_dot.add_point('idle', voltages={'virtual_dot_0': 0.1})
                quantum_dot.step_to_point('idle', duration=100)

                # Equivalent using macro (reusable, serializable)
                quantum_dot.macros['idle'] = StepPointMacro('idle', 100)
                quantum_dot.macros['idle']()
        """
        full_name = self._create_point_name(point_name)
        self.voltage_sequence.step_to_point(name=full_name, duration=duration)

    def ramp_to_point(
        self, point_name: str, ramp_duration: int, duration: Optional[int] = None
    ) -> None:
        """
        Ramp gradually to a pre-defined voltage point (convenience method).

        This is a convenience wrapper around voltage_sequence.ramp_to_point()
        that handles automatic name prefixing. For reusable operations, consider
        creating a RampPointMacro instead and storing it in self.macros.

        Args:
            point_name: Local point name (without prefix, must be added via add_point())
            ramp_duration: Time for voltage transition in nanoseconds
            duration: Hold duration at target in nanoseconds (default: uses point's default)

        Raises:
            KeyError: If the point has not been registered via add_point()

        Example:
            .. code-block:: python

                # Assume quantum_dot is a component with VoltagePointMacroMixin

                # Direct usage (convenience)
                quantum_dot.add_point('loading', voltages={'virtual_dot_0': 0.3})
                quantum_dot.ramp_to_point('loading', ramp_duration=500, duration=200)

                # Equivalent using macro (reusable, serializable)
                quantum_dot.macros['load'] = RampPointMacro('loading', 200, 500)
                quantum_dot.macros['load']()
        """
        full_name = self._create_point_name(point_name)
        self.voltage_sequence.ramp_to_point(
            name=full_name, duration=duration, ramp_duration=ramp_duration
        )

    def add_point_with_step_macro(
        self,
        macro_name: str,
        voltages: Optional[Dict[str, float]] = None,
        hold_duration: int = 100,
        point_duration: int = 16,
        replace_existing_point: bool = True,
    ) -> StepPointMacro:
        """
        Convenience method: Create a voltage point and StepPointMacro with reference in one step,
        or create a macro for an existing point.

        This method supports two use cases:
        1. Creating a new point with voltages (voltages provided)
        2. Creating a macro for an existing point (voltages=None)

        This method follows quam's Pulse → Macro → Operation pattern by:
        1. Creating a VoltageTuningPoint in gate_set.macros (or using existing one)
        2. Creating a StepPointMacro with a reference to that point
        3. Storing the macro in self.macros[macro_name]

        This is the recommended way to create voltage point macros, as it automatically
        handles reference creation and ensures proper serialization.

        Args:
            macro_name: Name for the macro (stored in self.macros[macro_name])
            voltages: Optional voltage values for each gate. If None, looks up existing point.
                     (see add_point() for format details)
            hold_duration: Duration to hold the target voltage (nanoseconds, default: 100)
            point_duration: Default duration stored in the VoltageTuningPoint (nanoseconds, default: 16)
            replace_existing_point: If True, overwrites existing point (default: True)

        Returns:
            StepPointMacro: The created macro instance

        Raises:
            KeyError: If voltages is None and the point doesn't exist in the gate set

        Example:
            .. code-block:: python

                # Assume quantum_dot is a component with VoltagePointMacroMixin

                # Use case 1: Create new point and macro together
                quantum_dot.add_point_with_step_macro(
                    'idle',
                    voltages={'virtual_dot_0': 0.1},
                    hold_duration=100
                )

                # Use case 2: Create macro for existing point
                quantum_dot.add_point('readout', voltages={'virtual_dot_0': 0.2})
                quantum_dot.add_point_with_step_macro('readout', hold_duration=200)

                # Execute the macros
                quantum_dot.macros['idle']()
                quantum_dot.macros['readout']()

                # Use in a sequence
                seq = SequenceMacro(name='init', macro_refs=())
                seq = seq.with_macro(quantum_dot, 'idle')
                seq(quantum_dot)
        """
        # Determine the full point name
        full_name = self._create_point_name(macro_name)

        if voltages is not None:
            # Case 1: Create new point
            full_name = self.add_point(
                point_name=macro_name,
                voltages=voltages,
                duration=point_duration,
                replace_existing_point=replace_existing_point,
            )
        else:
            # Case 2: Use existing point
            gate_set = self.voltage_sequence.gate_set
            existing_points = gate_set.get_macros()

            if full_name not in existing_points:
                raise KeyError(
                    f"Point '{macro_name}' (full name: '{full_name}') does not exist. "
                    f"Available points: {list(existing_points.keys())}. "
                    f"To create a new point, provide the 'voltages' parameter."
                )

        # Get reference to the point using quam's reference system
        point = self.voltage_sequence.gate_set.macros[full_name]
        point_ref = point.get_reference()

        # Create macro with reference
        macro = StepPointMacro(
            point_ref=point_ref,
            hold_duration=hold_duration,
        )

        # Store in macros dict
        self.macros[macro_name] = macro

        return macro

    def add_point_with_ramp_macro(
        self,
        macro_name: str,
        voltages: Optional[Dict[str, float]] = None,
        hold_duration: int = 100,
        ramp_duration: int = 16,
        point_duration: int = 16,
        replace_existing_point: bool = True,
    ) -> RampPointMacro:
        """
        Convenience method: Create a voltage point and RampPointMacro with reference in one step,
        or create a macro for an existing point.

        This method supports two use cases:
        1. Creating a new point with voltages (voltages provided)
        2. Creating a macro for an existing point (voltages=None)

        This method follows quam's Pulse → Macro → Operation pattern by:
        1. Creating a VoltageTuningPoint in gate_set.macros (or using existing one)
        2. Creating a RampPointMacro with a reference to that point
        3. Storing the macro in self.macros[macro_name]

        This is the recommended way to create voltage point macros, as it automatically
        handles reference creation and ensures proper serialization.

        Args:
            macro_name: Name for the macro (stored in self.macros[macro_name])
            voltages: Optional voltage values for each gate. If None, looks up existing point.
                     (see add_point() for format details)
            hold_duration: Duration to hold the target voltage (nanoseconds, default: 100)
            ramp_duration: Time for gradual voltage transition (nanoseconds, default: 16)
            point_duration: Default duration stored in the VoltageTuningPoint (nanoseconds, default: 16)
            replace_existing_point: If True, overwrites existing point (default: True)

        Returns:
            RampPointMacro: The created macro instance

        Raises:
            KeyError: If voltages is None and the point doesn't exist in the gate set

        Example:
            .. code-block:: python

                # Assume quantum_dot is a component with VoltagePointMacroMixin

                # Use case 1: Create new point and macro together
                quantum_dot.add_point_with_ramp_macro(
                    'load',
                    voltages={'virtual_dot_0': 0.3},
                    hold_duration=200,
                    ramp_duration=500
                )

                # Use case 2: Create macro for existing point
                quantum_dot.add_point('measure', voltages={'virtual_dot_0': 0.25})
                quantum_dot.add_point_with_ramp_macro('measure', hold_duration=300, ramp_duration=400)

                # Execute the macros: ramps over specified duration, holds for specified duration
                quantum_dot.macros['load']()
                quantum_dot.macros['measure']()

                # Use in a sequence
                seq = SequenceMacro(name='init', macro_refs=())
                seq = seq.with_macro(quantum_dot, 'load')
                seq(quantum_dot)
        """
        # Determine the full point name
        full_name = self._create_point_name(macro_name)

        if voltages is not None:
            # Case 1: Create new point
            full_name = self.add_point(
                point_name=macro_name,
                voltages=voltages,
                duration=point_duration,
                replace_existing_point=replace_existing_point,
            )
        else:
            # Case 2: Use existing point
            gate_set = self.voltage_sequence.gate_set
            existing_points = gate_set.get_macros()

            if full_name not in existing_points:
                raise KeyError(
                    f"Point '{macro_name}' (full name: '{full_name}') does not exist. "
                    f"Available points: {list(existing_points.keys())}. "
                    f"To create a new point, provide the 'voltages' parameter."
                )

        # Get reference to the point using quam's reference system
        point = self.voltage_sequence.gate_set.macros[full_name]
        point_ref = point.get_reference()

        # Create macro with reference
        macro = RampPointMacro(
            point_ref=point_ref,
            hold_duration=hold_duration,
            ramp_duration=ramp_duration,
        )

        # Store in macros dict
        self.macros[macro_name] = macro

        return macro

    def with_step_point(
        self,
        name: str,
        voltages: Optional[Dict[str, float]] = None,
        hold_duration: int = 100,
        point_duration: int = 16,
        replace_existing_point: bool = True,
    ) -> "VoltagePointMacroMixin":
        """
        Fluent API: Add a voltage point with step macro and return self for chaining,
        or create a macro for an existing point.

        This is a convenience wrapper around add_point_with_step_macro() that
        returns self to enable method chaining for defining multiple macros.

        Supports two use cases:
        1. Creating a new point with voltages (voltages provided)
        2. Creating a macro for an existing point (voltages=None)

        Args:
            name: Name for both the point and the macro
            voltages: Optional voltage values for each gate. If None, looks up existing point.
            hold_duration: Duration to hold the target voltage (nanoseconds, default: 100)
            point_duration: Default duration stored in VoltageTuningPoint (nanoseconds, default: 16)
            replace_existing_point: If True, overwrites existing point (default: True)

        Returns:
            self: The component instance for method chaining

        Raises:
            KeyError: If voltages is None and the point doesn't exist

        Example:
            .. code-block:: python

                # Use case 1: Create new points with macros
                (component
                    .with_step_point("idle", {"gate": 0.1}, hold_duration=100)
                    .with_step_point("measure", {"gate": 0.2}, hold_duration=200)
                    .with_sequence("init", ["idle", "measure"]))

                # Use case 2: Create macro for existing point
                component.add_point("readout", {"gate": 0.15})
                component.with_step_point("readout", hold_duration=300)

                # Use in QUA program
                with program() as prog:
                    component.idle()
                    component.measure()
                    component.readout()
                    component.init()
        """
        self.add_point_with_step_macro(
            macro_name=name,
            voltages=voltages,
            hold_duration=hold_duration,
            point_duration=point_duration,
            replace_existing_point=replace_existing_point,
        )
        return self

    def with_ramp_point(
        self,
        name: str,
        voltages: Optional[Dict[str, float]] = None,
        hold_duration: int = 100,
        ramp_duration: int = 16,
        point_duration: int = 16,
        replace_existing_point: bool = True,
    ) -> "VoltagePointMacroMixin":
        """
        Fluent API: Add a voltage point with ramp macro and return self for chaining,
        or create a macro for an existing point.

        This is a convenience wrapper around add_point_with_ramp_macro() that
        returns self to enable method chaining for defining multiple macros.

        Supports two use cases:
        1. Creating a new point with voltages (voltages provided)
        2. Creating a macro for an existing point (voltages=None)

        Args:
            name: Name for both the point and the macro
            voltages: Optional voltage values for each gate. If None, looks up existing point.
            hold_duration: Duration to hold the target voltage (nanoseconds, default: 100)
            ramp_duration: Time for gradual voltage transition (nanoseconds, default: 16)
            point_duration: Default duration stored in VoltageTuningPoint (nanoseconds, default: 16)
            replace_existing_point: If True, overwrites existing point (default: True)

        Returns:
            self: The component instance for method chaining

        Raises:
            KeyError: If voltages is None and the point doesn't exist

        Example:
            .. code-block:: python

                # Use case 1: Create new points with macros
                (component
                    .with_ramp_point("load", {"gate": 0.3}, hold_duration=200, ramp_duration=500)
                    .with_step_point("readout", {"gate": 0.15}, hold_duration=1000)
                    .with_sequence("load_and_read", ["load", "readout"]))

                # Use case 2: Create macro for existing point
                component.add_point("measure", {"gate": 0.25})
                component.with_ramp_point("measure", hold_duration=300, ramp_duration=400)

                # Use in QUA program
                with program() as prog:
                    component.load()
                    component.readout()
                    component.measure()
                    component.load_and_read()
        """
        self.add_point_with_ramp_macro(
            macro_name=name,
            voltages=voltages,
            hold_duration=hold_duration,
            ramp_duration=ramp_duration,
            point_duration=point_duration,
            replace_existing_point=replace_existing_point,
        )
        return self

    def with_sequence(
        self,
        name: str,
        macro_names: List[str],
        description: Optional[str] = None,
        return_index: Optional[int] = None,
    ) -> "VoltagePointMacroMixin":
        """
        Fluent API: Create a sequence macro from existing macros and return self for chaining.

        This method creates a SequenceMacro that executes multiple macros in order.
        All referenced macros must already exist in self.macros.

        Args:
            name: Name for the sequence macro
            macro_names: List of macro names to execute in sequence
            description: Optional description for the sequence

        Returns:
            self: The component instance for method chaining

        Raises:
            KeyError: If any macro in macro_names doesn't exist in self.macros

        Example:
            .. code-block:: python

                # Define points and sequence in one chain
                (component
                    .with_step_point("idle", {"gate": 0.1}, hold_duration=100)
                    .with_ramp_point("load", {"gate": 0.3}, hold_duration=200, ramp_duration=500)
                    .with_step_point("measure", {"gate": 0.15}, hold_duration=1000)
                    .with_sequence("full_cycle", ["idle", "load", "measure"]))

                # Call the sequence as a method
                with program() as prog:
                    component.full_cycle()

                # Or call individual steps
                with program() as prog:
                    component.idle()
                    component.load()
                    component.measure()
        """
        # Validate that all referenced macros exist
        for macro_name in macro_names:
            if macro_name not in self.macros:
                raise KeyError(
                    f"Cannot create sequence '{name}': macro '{macro_name}' not found. "
                    f"Available macros: {list(self.macros.keys())}"
                )

        # Create and register the sequence
        sequence = SequenceMacro(name=name, description=description, return_index=return_index).with_macros(
            self, macro_names
        )
        self.macros[name] = sequence

        return self

    def with_macro(
            self,
            name: str,
            macro: QuamMacro,
    ):

        # Store in macros dict
        self.macros[name] = macro

        return self

    def with_conditional_macro(
        self,
        name: str,
        measurement_macro: str,
        conditional_macro: str,
        invert_condition: bool = False,
        align_elements: Optional[List[str]] = None,
    ) -> "VoltagePointMacroMixin":
        """
        Fluent API: Add a conditional macro and return self for chaining.

        This creates a ConditionalMacro that executes a measurement and conditionally
        applies another macro based on the result.

        Args:
            name: Name for the conditional macro
            measurement_macro: Name of measurement macro in self.macros, or a reference string
            conditional_macro: Name of macro in self.macros, or a reference string (e.g., from get_reference())
            invert_condition: If False (default), apply when measurement is True.
                             If True, apply when measurement is False.

        Returns:
            self: The component instance for method chaining

        Raises:
            KeyError: If macro names don't exist (when not using references)

        Example:
            .. code-block:: python

                # Option 1: Use macro names (must exist in self.macros)
                component.with_conditional_macro(
                    name='reset',
                    measurement_macro='measure',
                    conditional_macro='x180',
                    invert_condition=False
                )

                # Option 2: Use reference strings (can reference macros from other components)
                component.with_conditional_macro(
                    name='reset',
                    measurement_macro='measure',  # Local macro
                    conditional_macro=component.qubit_target.macros["x180"].get_reference(),
                    invert_condition=False
                )

                # Option 3: Chain with other operations
                (component
                    .with_step_point("idle", {"gate": 0.1}, hold_duration=100)
                    .with_conditional_macro(
                        name='reset',
                        measurement_macro='measure',
                        conditional_macro='x180'
                    )
                    .with_sequence("init_with_reset", ["idle", "reset"]))

                # Execute in QUA program
                with program() as prog:
                    was_excited = component.reset()  # Conditional reset
                    component.init_with_reset()  # Full sequence
        """
        # Handle measurement_macro: check if it's a reference or macro name
        if measurement_macro.startswith('#'):
            # Already a reference string
            measurement_ref = measurement_macro
        else:
            # It's a macro name, validate and create reference
            if measurement_macro not in self.macros:
                raise KeyError(
                    f"Measurement macro '{measurement_macro}' not found in macros. "
                    f"Available macros: {list(self.macros.keys())}"
                )
            # Use #../ to reference sibling macros (go up from this macro to parent macros dict)
            measurement_ref = f"#../{measurement_macro}"

        # Handle conditional_macro: check if it's a reference or macro name
        if conditional_macro.startswith('#'):
            # Already a reference string
            conditional_ref = conditional_macro
        else:
            # It's a macro name, validate and create reference
            if conditional_macro not in self.macros:
                raise KeyError(
                    f"Conditional macro '{conditional_macro}' not found in macros. "
                    f"Available macros: {list(self.macros.keys())}"
                )
            # Use #../ to reference sibling macros (go up from this macro to parent macros dict)
            conditional_ref = f"#../{conditional_macro}"

        # Create the conditional macro
        macro = ConditionalMacro(
            measurement_macro=measurement_ref,
            conditional_macro=conditional_ref,
            invert_condition=invert_condition,
            # align_elements=align_elements
        )

        # Store in macros dict
        self.macros[name] = macro

        return self
