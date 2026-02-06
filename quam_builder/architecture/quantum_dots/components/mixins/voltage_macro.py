"""Full voltage macro mixin combining all voltage and macro functionality.

This module provides the complete API for voltage point macros, combining
voltage control, point management, and macro dispatch capabilities.
"""

from typing import TYPE_CHECKING, Dict, List, Optional

from quam.core import quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.macros import (
    SequenceMacro,
    StepPointMacro,
    RampPointMacro,
    ConditionalMacro,
)

from .voltage_point import VoltagePointMixin
from .macro_dispatch import MacroDispatchMixin

if TYPE_CHECKING:
    pass

__all__ = ["VoltageMacroMixin"]


@quam_dataclass
class VoltageMacroMixin(VoltagePointMixin, MacroDispatchMixin):
    """Full mixin providing voltage point macro methods for quantum dot components.

    This mixin consolidates all voltage control methods to reduce code duplication
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
        class MyComponent(QuamComponent, VoltageMacroMixin):
            id: str
            physical_channel: VoltageGate
            points: Dict[str, Dict[str, float]] = field(default_factory=dict)

            @property
            def voltage_sequence(self) -> VoltageSequence:
                # Implementation to return voltage sequence
                ...

        # Define macros during calibration
        component.with_step_point("idle", {"gate": 0.1}, duration=100)
        component.with_ramp_point("load", {"gate": 0.3}, duration=200, ramp_duration=500)
        component.with_sequence("init", ["idle", "load"])

        # Call as methods in QUA program
        with program() as prog:
            component.idle()  # Calls StepPointMacro
            component.load()  # Calls RampPointMacro
            component.init()  # Calls SequenceMacro
    """

    def add_point_with_step_macro(
        self,
        macro_name: str,
        voltages: Optional[Dict[str, float]] = None,
        duration: int = 100,
        replace_existing_point: bool = True,
    ) -> StepPointMacro:
        """Convenience method: Create a voltage point and StepPointMacro in one step.

        This method supports two use cases:
        1. Creating a new point with voltages (voltages provided)
        2. Creating a macro for an existing point (voltages=None)

        This method follows quam's Pulse -> Macro -> Operation pattern by:
        1. Creating a VoltageTuningPoint in gate_set.macros (or using existing one)
        2. Creating a StepPointMacro with a reference to that point
        3. Storing the macro in self.macros[macro_name]

        Args:
            macro_name: Name for the macro (stored in self.macros[macro_name])
            voltages: Optional voltage values for each gate. If None, looks up existing point.
            duration: Duration to hold the target voltage (nanoseconds, default: 100).
            replace_existing_point: If True, overwrites existing point (default: True)

        Returns:
            StepPointMacro: The created macro instance

        Raises:
            KeyError: If voltages is None and the point doesn't exist in the gate set

        Example:
            .. code-block:: python

                # Use case 1: Create new point and macro together
                quantum_dot.add_point_with_step_macro(
                    'idle',
                    voltages={'virtual_dot_0': 0.1},
                    duration=100
                )

                # Use case 2: Create macro for existing point
                quantum_dot.add_point('readout', voltages={'virtual_dot_0': 0.2}, duration=200)
                quantum_dot.add_point_with_step_macro('readout')

                # Execute the macros
                quantum_dot.macros['idle']()
                quantum_dot.macros['readout']()
        """
        point_ref = self._get_or_create_point_ref(
            macro_name, voltages, duration, replace_existing_point
        )
        macro = StepPointMacro(point_ref=point_ref)
        self.macros[macro_name] = macro
        return macro

    def add_point_with_ramp_macro(
        self,
        macro_name: str,
        voltages: Optional[Dict[str, float]] = None,
        duration: int = 100,
        ramp_duration: int = 16,
        replace_existing_point: bool = True,
    ) -> RampPointMacro:
        """Convenience method: Create a voltage point and RampPointMacro in one step.

        This method supports two use cases:
        1. Creating a new point with voltages (voltages provided)
        2. Creating a macro for an existing point (voltages=None)

        This method follows quam's Pulse -> Macro -> Operation pattern by:
        1. Creating a VoltageTuningPoint in gate_set.macros (or using existing one)
        2. Creating a RampPointMacro with a reference to that point
        3. Storing the macro in self.macros[macro_name]

        Args:
            macro_name: Name for the macro (stored in self.macros[macro_name])
            voltages: Optional voltage values for each gate. If None, looks up existing point.
            duration: Duration to hold the target voltage (nanoseconds, default: 100).
            ramp_duration: Time for gradual voltage transition (nanoseconds, default: 16).
            replace_existing_point: If True, overwrites existing point (default: True)

        Returns:
            RampPointMacro: The created macro instance

        Raises:
            KeyError: If voltages is None and the point doesn't exist in the gate set

        Example:
            .. code-block:: python

                # Use case 1: Create new point and macro together
                quantum_dot.add_point_with_ramp_macro(
                    'load',
                    voltages={'virtual_dot_0': 0.3},
                    duration=200,
                    ramp_duration=500
                )

                # Use case 2: Create macro for existing point
                quantum_dot.add_point('measure', voltages={'virtual_dot_0': 0.25}, duration=300)
                quantum_dot.add_point_with_ramp_macro('measure', ramp_duration=400)

                # Execute the macros
                quantum_dot.macros['load']()
                quantum_dot.macros['measure']()
        """
        point_ref = self._get_or_create_point_ref(
            macro_name, voltages, duration, replace_existing_point
        )
        macro = RampPointMacro(point_ref=point_ref, ramp_duration=ramp_duration)
        self.macros[macro_name] = macro
        return macro

    def with_step_point(
        self,
        name: str,
        voltages: Optional[Dict[str, float]] = None,
        duration: int = 100,
        replace_existing_point: bool = True,
    ) -> "VoltageMacroMixin":
        """Fluent API: Add a voltage point with step macro and return self for chaining.

        This is a convenience wrapper around add_point_with_step_macro() that
        returns self to enable method chaining for defining multiple macros.

        Supports two use cases:
        1. Creating a new point with voltages (voltages provided)
        2. Creating a macro for an existing point (voltages=None)

        Args:
            name: Name for both the point and the macro
            voltages: Optional voltage values for each gate. If None, looks up existing point.
            duration: Duration to hold the target voltage (nanoseconds, default: 100)
            replace_existing_point: If True, overwrites existing point (default: True)

        Returns:
            self: The component instance for method chaining

        Raises:
            KeyError: If voltages is None and the point doesn't exist

        Example:
            .. code-block:: python

                # Use case 1: Create new points with macros
                (component
                    .with_step_point("idle", {"gate": 0.1}, duration=100)
                    .with_step_point("measure", {"gate": 0.2}, duration=200)
                    .with_sequence("init", ["idle", "measure"]))

                # Use case 2: Create macro for existing point
                component.add_point("readout", {"gate": 0.15}, duration=300)
                component.with_step_point("readout")

                # Use in QUA program
                with program() as prog:
                    component.idle()
                    component.measure()
        """
        self.add_point_with_step_macro(
            macro_name=name,
            voltages=voltages,
            duration=duration,
            replace_existing_point=replace_existing_point,
        )
        return self

    def with_ramp_point(
        self,
        name: str,
        voltages: Optional[Dict[str, float]] = None,
        duration: int = 100,
        ramp_duration: int = 16,
        replace_existing_point: bool = True,
    ) -> "VoltageMacroMixin":
        """Fluent API: Add a voltage point with ramp macro and return self for chaining.

        This is a convenience wrapper around add_point_with_ramp_macro() that
        returns self to enable method chaining for defining multiple macros.

        Supports two use cases:
        1. Creating a new point with voltages (voltages provided)
        2. Creating a macro for an existing point (voltages=None)

        Args:
            name: Name for both the point and the macro
            voltages: Optional voltage values for each gate. If None, looks up existing point.
            duration: Duration to hold the target voltage (nanoseconds, default: 100)
            ramp_duration: Time for gradual voltage transition (nanoseconds, default: 16)
            replace_existing_point: If True, overwrites existing point (default: True)

        Returns:
            self: The component instance for method chaining

        Raises:
            KeyError: If voltages is None and the point doesn't exist

        Example:
            .. code-block:: python

                # Use case 1: Create new points with macros
                (component
                    .with_ramp_point("load", {"gate": 0.3}, duration=200, ramp_duration=500)
                    .with_step_point("readout", {"gate": 0.15}, duration=1000)
                    .with_sequence("load_and_read", ["load", "readout"]))

                # Use case 2: Create macro for existing point
                component.add_point("measure", {"gate": 0.25}, duration=300)
                component.with_ramp_point("measure", ramp_duration=400)

                # Use in QUA program
                with program() as prog:
                    component.load()
                    component.readout()
        """
        self.add_point_with_ramp_macro(
            macro_name=name,
            voltages=voltages,
            duration=duration,
            ramp_duration=ramp_duration,
            replace_existing_point=replace_existing_point,
        )
        return self

    def with_sequence(
        self,
        name: str,
        macro_names: List[str],
        description: Optional[str] = None,
        return_index: Optional[int] = None,
    ) -> "VoltageMacroMixin":
        """Fluent API: Create a sequence macro from existing macros and return self for chaining.

        This method creates a SequenceMacro that executes multiple macros in order.
        All referenced macros must already exist in self.macros.

        Args:
            name: Name for the sequence macro
            macro_names: List of macro names to execute in sequence
            description: Optional description for the sequence
            return_index: Optional index of macro whose return value to return

        Returns:
            self: The component instance for method chaining

        Raises:
            KeyError: If any macro in macro_names doesn't exist in self.macros

        Example:
            .. code-block:: python

                # Define points and sequence in one chain
                (component
                    .with_step_point("idle", {"gate": 0.1}, duration=100)
                    .with_ramp_point("load", {"gate": 0.3}, duration=200, ramp_duration=500)
                    .with_step_point("measure", {"gate": 0.15}, duration=1000)
                    .with_sequence("full_cycle", ["idle", "load", "measure"]))

                # Call the sequence as a method
                with program() as prog:
                    component.full_cycle()
        """
        # Validate that all referenced macros exist
        for macro_name in macro_names:
            if macro_name not in self.macros:
                raise KeyError(
                    f"Cannot create sequence '{name}': macro '{macro_name}' not found. "
                    f"Available macros: {list(self.macros.keys())}"
                )

        # Create and register the sequence
        sequence = SequenceMacro(
            name=name, description=description, return_index=return_index
        ).with_macros(self, macro_names)
        self.macros[name] = sequence

        return self

    def with_macro(
        self,
        name: str,
        macro: QuamMacro,
    ) -> "VoltageMacroMixin":
        """Fluent API: Add an arbitrary macro and return self for chaining.

        Args:
            name: Name to store the macro under
            macro: The macro instance to add

        Returns:
            self: The component instance for method chaining
        """
        self.macros[name] = macro
        return self

    def with_conditional_macro(
        self,
        name: str,
        measurement_macro: str,
        conditional_macro: str,
        invert_condition: bool = False,
    ) -> "VoltageMacroMixin":
        """Fluent API: Add a conditional macro and return self for chaining.

        This creates a ConditionalMacro that executes a measurement and conditionally
        applies another macro based on the result.

        Args:
            name: Name for the conditional macro
            measurement_macro: Name of measurement macro in self.macros, or a reference string
            conditional_macro: Name of macro in self.macros, or a reference string
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

                # Option 2: Use reference strings
                component.with_conditional_macro(
                    name='reset',
                    measurement_macro='measure',  # Local macro
                    conditional_macro=component.qubit_target.macros["x180"].get_reference(),
                    invert_condition=False
                )

                # Execute in QUA program
                with program() as prog:
                    was_excited = component.reset()
        """
        measurement_ref = self._resolve_macro_ref(measurement_macro, "Measurement macro")
        conditional_ref = self._resolve_macro_ref(conditional_macro, "Conditional macro")

        macro = ConditionalMacro(
            measurement_macro=measurement_ref,
            conditional_macro=conditional_ref,
            invert_condition=invert_condition,
        )
        self.macros[name] = macro

        return self
