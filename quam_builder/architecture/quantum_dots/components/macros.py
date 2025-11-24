"""
Mixin classes for voltage point macro functionality.

This module provides mixin classes that implement common voltage point macro methods
to reduce code duplication across quantum dot components.
"""

from typing import Dict, TYPE_CHECKING, Optional, List
from dataclasses import dataclass, field

from quam.core import quam_dataclass, QuamComponent
from quam.components import QuantumComponent
from quam.utils import string_reference
from quam.utils.exceptions import InvalidReferenceError

from quam_builder.tools.qua_tools import DurationType, VoltageLevelType
if TYPE_CHECKING:
    from quam_builder.tools.voltage_sequence import VoltageSequence
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

__all__ = [
    "VoltagePointMacroMixin",
    "SequenceMacro",
    "StepPointMacro",
    "RampPointMacro",
]

from quam.core.macro.quam_macro import QuamMacro
from quam.core.operation.operations_registry import OperationsRegistry

@quam_dataclass
class BasePointMacro(QuamMacro):
    """
    Base class for voltage point macros following quam's Pulse → Macro → Operation pattern.

    Voltage point macros encapsulate operations on pre-defined voltage points (VoltageTuningPoint)
    stored in the gate set. Following quam conventions, macros store references to voltage points
    rather than concrete instances, enabling:
    - Serialization-friendly storage (references preserved as strings in JSON)
    - Single source of truth (point definitions in gate_set.macros)
    - Automatic updates when point definitions change

    The reference pattern mirrors quam's PulseMacro → Pulse relationship:
    - VoltageTuningPoint ≈ Pulse (primitive definition)
    - PointMacro ≈ PulseMacro (wrapper with reference)
    - Sequence/Operation ≈ Gate (composed operations)

    Attributes:
        point_ref: Reference string to VoltageTuningPoint in gate_set.macros
                  (e.g., "#./voltage_sequence/gate_set/macros/quantum_dot_0_idle").
                  Set to None if using legacy point_name approach.
        hold_duration: Duration to hold the final voltage (nanoseconds).
        macro_type: Type identifier ('step', 'ramp', etc.).

    Example:
        .. code-block:: python

            # Assume quantum_dot is a component with VoltagePointMacroMixin

            # Define a point (stored in gate_set.macros)
            full_name = quantum_dot.add_point('idle', voltages={'virtual_dot_0': 0.1})
            # Returns: 'quantum_dot_0_idle'

            # Create macro with reference to the point
            point_ref = f"#./voltage_sequence/gate_set/macros/{full_name}"
            quantum_dot.macros['idle'] = StepPointMacro(
                point_ref=point_ref,
                hold_duration=100
            )

            # Execute directly (obj parameter optional, uses self.parent)
            quantum_dot.macros['idle']()

            # Or use in a sequence
            sequence = SequenceMacro(name='init', macro_refs=())
            sequence = sequence.with_macro(quantum_dot, 'idle')
            sequence(quantum_dot)

            # Convenience: Use helper method to create point+macro together
            quantum_dot.add_point_with_step_macro('idle', voltages={'virtual_dot_0': 0.1}, hold_duration=100)
    """

    point_ref: Optional[str] = None
    hold_duration: int = None
    macro_type: str = "base"

    def _resolve_point(self, component: QuamComponent):
        """
        Resolve the point reference to get the actual VoltageTuningPoint object.

        Args:
            component: The component from which to resolve (typically the parent quantum dot)

        Returns:
            VoltageTuningPoint: The resolved voltage tuning point

        Raises:
            ValueError: If point_ref is not set
            TypeError: If reference doesn't resolve to VoltageTuningPoint
            InvalidReferenceError: If reference cannot be resolved
        """
        from quam_builder.architecture.quantum_dots.components.gate_set import VoltageTuningPoint

        if self.point_ref is None:
            raise ValueError("point_ref is not set on this macro")

        try:
            point = string_reference.get_referenced_value(
                component,
                self.point_ref,
                root=component.get_root(),
            )
        except (InvalidReferenceError, AttributeError) as e:
            raise InvalidReferenceError(
                f"Could not resolve point reference '{self.point_ref}' from {component}: {e}"
            )

        if not isinstance(point, VoltageTuningPoint):
            raise TypeError(
                f"Reference '{self.point_ref}' resolved to {type(point).__name__}, "
                f"expected VoltageTuningPoint"
            )

        return point

    def _get_point_name(self) -> str:
        """
        Get the full point name from the reference.

        This extracts the last segment of the reference path, which corresponds
        to the key in gate_set.macros (e.g., "quantum_dot_0_idle").

        Args:
            component: The component from which to resolve the reference

        Returns:
            str: The full point name (e.g., "quantum_dot_0_idle")
        """
        # Access raw attribute value to avoid QUAM's automatic reference resolution
        point_ref_raw = object.__getattribute__(self, '__dict__').get('point_ref')
        if point_ref_raw is None:
            raise ValueError("point_ref is not set on this macro")

        # Extract the last segment from reference path
        # E.g., "#./voltage_sequence/gate_set/macros/quantum_dot_0_idle" -> "quantum_dot_0_idle"
        return point_ref_raw.split('/')[-1]

    def __call__(self, **overrides):
        """
        Allow macros to be invoked as callables (quam convention).

        Args:
            **overrides: Optional parameter overrides (hold_duration, ramp_duration, etc.)
                        'duration' is accepted as alias for 'hold_duration' for compatibility.

        Returns:
            Result of apply() method

        Raises:
            ValueError: If self.parent is not set (macro must be attached to a component)
        """
        # Ensure macro is attached to a component
        if not hasattr(self, 'parent') or self.parent is None:
            raise ValueError(
                f"Cannot execute macro: macro has no parent. "
                f"Ensure the macro is attached to a component via component.macros['name'] = macro"
            )

        # Support 'duration' as alias for 'hold_duration' for compatibility
        if "duration" in overrides and "hold_duration" not in overrides:
            overrides["hold_duration"] = overrides.pop("duration")

        return self.apply(**overrides)


@quam_dataclass
class StepPointMacro(BasePointMacro):
    """
    Macro that executes a step (instantaneous) voltage transition to a registered point.

    A step operation changes voltage instantly (limited only by hardware rise time)
    and holds at the target for the specified duration. This is the fastest way
    to change voltages when adiabaticity is not required.

    Following quam's reference pattern, this macro stores a reference to a VoltageTuningPoint
    rather than the point name directly, enabling serialization and automatic updates.

    Attributes:
        point_ref: Reference to VoltageTuningPoint in gate_set.macros
        hold_duration: Time to hold at the target voltage (nanoseconds)
        macro_type: Always "step" for this class

    Example:
        .. code-block:: python

            # Assume quantum_dot is a component with VoltagePointMacroMixin

            # Method 1: Manual creation with reference
            full_name = quantum_dot.add_point('idle', voltages={'virtual_dot_0': 0.1}, duration=16)
            point_ref = f"#./voltage_sequence/gate_set/macros/{full_name}"
            quantum_dot.macros['idle'] = StepPointMacro(
                point_ref=point_ref,
                hold_duration=100
            )

            # Method 2: Use convenience helper (recommended)
            quantum_dot.add_point_with_step_macro(
                'idle',
                voltages={'virtual_dot_0': 0.1},
                hold_duration=100
            )

            # Execute: instantly steps to idle, holds for 100ns
            quantum_dot.macros['idle']()

            # Or use in a sequence
            seq = SequenceMacro(name='init', macro_refs=())
            seq = seq.with_macro(quantum_dot, 'idle')
    """

    macro_type: str = "step"

    @property
    def inferred_duration(self) -> Optional[float]:
        """Return total duration of the step operation in seconds."""
        return self.hold_duration * 1e-9 if self.hold_duration is not None else None

    def apply(self, hold_duration: Optional[int] = None):
        """
        Execute the step operation on the component this macro is attached to.

        Args:
            hold_duration: Optional override for hold duration (nanoseconds)
        """
        duration = hold_duration if hold_duration is not None else self.hold_duration
        # Get the full point name from the reference
        point_name = self._get_point_name()
        # Access voltage_sequence via parent (the component this macro is attached to)
        self.parent.parent.voltage_sequence.step_to_point(point_name, duration=duration)


@quam_dataclass
class RampPointMacro(BasePointMacro):
    """
    Macro that executes a ramp (gradual) voltage transition to a registered point.

    A ramp operation changes voltage gradually over the specified ramp duration,
    then holds at the target for the hold duration. This is essential for
    adiabatic transitions where quantum states must evolve smoothly.

    Following quam's reference pattern, this macro stores a reference to a VoltageTuningPoint
    rather than the point name directly, enabling serialization and automatic updates.

    Attributes:
        point_ref: Reference to VoltageTuningPoint in gate_set.macros
        hold_duration: Time to hold at the target voltage (nanoseconds)
        ramp_duration: Time for gradual voltage transition (nanoseconds, default: 16)
        macro_type: Always "ramp" for this class

    Example:
        .. code-block:: python

            # Assume quantum_dot is a component with VoltagePointMacroMixin

            # Method 1: Manual creation with reference
            full_name = quantum_dot.add_point('loading', voltages={'virtual_dot_0': 0.3}, duration=16)
            point_ref = f"#./voltage_sequence/gate_set/macros/{full_name}"
            quantum_dot.macros['load'] = RampPointMacro(
                point_ref=point_ref,
                hold_duration=200,
                ramp_duration=500
            )

            # Method 2: Use convenience helper (recommended)
            quantum_dot.add_point_with_ramp_macro(
                'load',
                voltages={'virtual_dot_0': 0.3},
                hold_duration=200,
                ramp_duration=500
            )

            # Execute: ramps over 500ns, holds for 200ns (total: 700ns)
            quantum_dot.macros['load']()

            # Use in sequence
            seq = SequenceMacro(name='init', macro_refs=())
            seq = seq.with_macro(quantum_dot, 'load')
    """

    macro_type: str = "ramp"
    ramp_duration: int = 16

    @property
    def inferred_duration(self) -> Optional[float]:
        """Return total duration (ramp + hold) in seconds."""
        if self.ramp_duration is None or self.hold_duration is None:
            return None
        return (self.ramp_duration + self.hold_duration) * 1e-9

    def apply(
        self,
        hold_duration: Optional[int] = None,
        ramp_duration: Optional[int] = None,
    ):
        """
        Execute the ramp operation on the component this macro is attached to.

        Args:
            hold_duration: Optional override for hold duration (nanoseconds)
            ramp_duration: Optional override for ramp duration (nanoseconds)
        """
        ramp_ns = ramp_duration if ramp_duration is not None else self.ramp_duration
        hold_ns = hold_duration if hold_duration is not None else self.hold_duration
        # Get the full point name from the reference
        point_name = self._get_point_name()
        # Access voltage_sequence via parent (the component this macro is attached to)
        self.parent.parent.voltage_sequence.ramp_to_point(
            point_name,
            ramp_duration=ramp_ns,
            duration=hold_ns,
        )

@quam_dataclass
class SequenceMacro(QuamMacro):
    """
    Macro that executes an ordered list of other macros in sequence.

    SequenceMacro acts as a lightweight container that preserves serialization
    friendliness by storing only the composed macros. Any QuamMacro (PointMacro,
    PulseMacro, etc.) can participate, making it easy to stitch voltage and pulse
    operations together following QUAM conventions.

    Key conveniences:
    - ``with_reference(ref: str)`` appends an existing reference string.
    - ``with_macro(owner, name)``/
      ``with_macros(owner, [names...])`` look up macros by name on ``owner.macros``,
      create the reference, and append. This avoids manually typing reference paths.
    - All references are standard QUAM reference strings (e.g. ``#./macros/foo``),
      so edits to referenced macros propagate automatically, including after
      serialization/deserialization.
    """

    name: str
    macro_refs: tuple[str, ...] = field(default_factory=tuple)
    description: Optional[str] = None

    def __call__(self, *args, **kwargs):
        self.apply(*args, **kwargs)

    def with_reference(self, reference: str) -> "SequenceMacro":
        """Return a new SequenceMacro with the provided reference appended."""
        return SequenceMacro(
            name=self.name,
            macro_refs=self.macro_refs + (reference,),
            description=self.description,
        )

    def with_macro(
        self,
        owner: QuamComponent,
        macro_name: str,
    ) -> "SequenceMacro":
        """Append a macro by name, creating/using its reference on the owner."""
        reference = self._reference_for(owner, macro_name)
        return self.with_reference(reference)

    def with_macros(
        self,
        owner: QuamComponent,
        macro_names: List[str],
    ) -> "SequenceMacro":
        """
        Convenience helper: append multiple macros by name.
        """
        sequence = self
        for macro_name in macro_names:
            sequence = sequence.with_macro(owner, macro_name)
        return sequence

    @staticmethod
    def _reference_for(
        owner: QuamComponent,
        macro_name: str,
    ) -> str:
        """
        Create or reuse a reference for a macro name on the owner.
        Sequences are also stored under the macros dict for a unified namespace.
        """
        macros = getattr(owner, "macros", None)
        if macros is None:
            macros = {}
            setattr(owner, "macros", macros)

        if macro_name not in macros:
            raise KeyError(f"Macro '{macro_name}' not found on owner {owner}")

        return f"#./macros/{macro_name}"

    def resolved_macros(self, component: QuamComponent) -> List[QuamMacro]:
        """Resolve stored references to concrete macros."""
        resolved: List[QuamMacro] = []
        for reference in self.macro_refs:
            try:
                resolved_macro = string_reference.get_referenced_value(
                    component,
                    reference,
                    root=component.get_root(),
                )
            except (InvalidReferenceError, AttributeError):
                raise InvalidReferenceError(
                    f"Could not resolve reference '{reference}' for sequence '{self.name}'"
                )
            resolved.append(resolved_macro)
        return resolved

    def apply(self, **kwargs):
        """Execute each referenced macro sequentially on the provided component."""
        # Resolve macros using self.parent (the component that owns this sequence)
        for macro in self.resolved_macros(self.parent.parent):
            macro.apply(**kwargs)

    def register_operation(
        self,
        registry: OperationsRegistry,
        operation_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Register this sequence as an operation."""
        op_name = operation_name or self.name

        def operation_fn(component: QuamComponent):
            """Execute the sequence via the operations registry."""
            sequence = component.sequences[self.name]
            sequence(component)

        operation_fn.__doc__ = description or self.description or f"Execute '{self.name}' sequence."
        operation_fn.__name__ = op_name
        registry.register_operation(op_name)(operation_fn)

    def total_duration_seconds(
        self, component: QuamComponent
    ) -> Optional[float]:
        """Return the summed duration of all referenced macros if available."""
        durations: List[Optional[float]] = []
        for macro in self.resolved_macros(component):
            duration = getattr(macro, "inferred_duration", None)
            if duration is None:
                duration = getattr(macro, "duration", None)
            durations.append(duration)
        if any(duration is None for duration in durations):
            return None
        return sum(duration for duration in durations if duration is not None)  # type: ignore[arg-type]


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
                macros_dict = object.__getattribute__(self, '__dict__').get('macros', {})
                if macros_dict and name in macros_dict:
                    # Return a bound method-like callable
                    # Note: apply() uses self.parent internally, no need to pass component
                    def macro_method(**kwargs):
                        return macros_dict[name].apply(**kwargs)
                    macro_method.__name__ = name
                    macro_method.__doc__ = getattr(macros_dict[name], '__doc__', f'Execute {name} macro')
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

    def _validate_voltage_sequence(self) -> None:
        """Validate that voltage_sequence is available."""
        if self.voltage_sequence is None:
            component_name = self.__class__.__name__
            component_id = self.id
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

    def go_to_voltages(self, voltages : Dict[str, VoltageLevelType], duration: DurationType) -> None:
        """
        Agnostic function to set voltage in a sequence.simultaneous block.

        Whether it is a step or a ramp should be determined by the context manager.
        This method is intended for use within a simultaneous block.

        Args:
            voltage: Target voltage in volts
            duration: Duration to hold the voltage in nanoseconds (default: 16)
        """
        self.voltage_sequence.step_to_voltages(
            voltages, duration=duration
        )

    def step_to_voltages(self, voltages : Dict[str, VoltageLevelType], duration: DurationType) -> None:
        """
        Step to a specified voltage.

        Args:
            voltage: Target voltage in volts
            duration: Duration to hold the voltage in nanoseconds (default: 16)
        """
        self.voltage_sequence.step_to_voltages(
            voltages, duration=duration
        )

    def ramp_to_voltages(
        self, voltages : Dict[str, VoltageLevelType], duration: DurationType, ramp_duration: DurationType
    ) -> None:
        """
        Ramp to a specified voltage.

        Args:
            voltage: Target voltage in volts
            ramp_duration: Duration of the ramp in nanoseconds
            duration: Duration to hold the final voltage in nanoseconds (default: 16)
        """
        self.voltage_sequence.ramp_to_voltages(
            voltages, duration, ramp_duration
        )

    def add_point(
        self,
        point_name: str,
        voltages: Dict[str, float],
        duration: int = 16,
        replace_existing_point: bool = False,
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
            replace_existing_point: If True, overwrites existing point with same name.
                                   If False (default), raises ValueError if point exists.

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
            component_type = self.__class__.__name__
            raise ValueError(
                f"Point '{point_name}' already exists as '{full_name}'. "
                "Set replace_existing_point=True to overwrite."
            )

        # Register in gate set
        gate_set.add_point(
            name=full_name,
            voltages=voltages,
            duration=duration
        )

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

    def step_to_point(self, point_name: str, duration: int = None) -> None:
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
        self, point_name: str, ramp_duration: int, duration: int = None
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
            name=full_name,
            duration=duration,
            ramp_duration=ramp_duration
        )

    def _add_point_with_step_macro(
        self,
        macro_name: str,
        voltages: Dict[str, float],
        hold_duration: int,
        point_duration: int = 16,
        replace_existing_point: bool = False,
    ) -> StepPointMacro:
        """
        Convenience method: Create a voltage point and StepPointMacro with reference in one step.

        This method follows quam's Pulse → Macro → Operation pattern by:
        1. Creating a VoltageTuningPoint in gate_set.macros
        2. Creating a StepPointMacro with a reference to that point
        3. Storing the macro in self.macros[macro_name]

        This is the recommended way to create voltage point macros, as it automatically
        handles reference creation and ensures proper serialization.

        Args:
            macro_name: Name for the macro (stored in self.macros[macro_name])
            voltages: Voltage values for each gate (see add_point() for format details)
            hold_duration: Duration to hold the target voltage (nanoseconds)
            point_duration: Default duration stored in the VoltageTuningPoint (nanoseconds, default: 16)
            replace_existing_point: If True, overwrites existing point (default: False)

        Returns:
            StepPointMacro: The created macro instance

        Example:
            .. code-block:: python

                # Assume quantum_dot is a component with VoltagePointMacroMixin

                # Create point and macro together (recommended)
                quantum_dot.add_point_with_step_macro(
                    'idle',
                    voltages={'virtual_dot_0': 0.1},
                    hold_duration=100
                )

                # Execute the macro
                quantum_dot.macros['idle']()

                # Use in a sequence
                seq = SequenceMacro(name='init', macro_refs=())
                seq = seq.with_macro(quantum_dot, 'idle')
                seq(quantum_dot)
        """
        # Create the voltage point
        full_name = self.add_point(
            point_name=macro_name,
            voltages=voltages,
            duration=point_duration,
            replace_existing_point=replace_existing_point,
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

        # Set parent for proper reference resolution
        # if hasattr(macro, "parent"):
        #     macro.parent = None
        #     macro.parent = self

        return macro

    def _add_point_with_ramp_macro(
        self,
        macro_name: str,
        voltages: Dict[str, float],
        hold_duration: int,
        ramp_duration: int,
        point_duration: int = 16,
        replace_existing_point: bool = False,
    ) -> RampPointMacro:
        """
        Convenience method: Create a voltage point and RampPointMacro with reference in one step.

        This method follows quam's Pulse → Macro → Operation pattern by:
        1. Creating a VoltageTuningPoint in gate_set.macros
        2. Creating a RampPointMacro with a reference to that point
        3. Storing the macro in self.macros[macro_name]

        This is the recommended way to create voltage point macros, as it automatically
        handles reference creation and ensures proper serialization.

        Args:
            macro_name: Name for the macro (stored in self.macros[macro_name])
            voltages: Voltage values for each gate (see add_point() for format details)
            hold_duration: Duration to hold the target voltage (nanoseconds)
            ramp_duration: Time for gradual voltage transition (nanoseconds)
            point_duration: Default duration stored in the VoltageTuningPoint (nanoseconds, default: 16)
            replace_existing_point: If True, overwrites existing point (default: False)

        Returns:
            RampPointMacro: The created macro instance

        Example:
            .. code-block:: python

                # Assume quantum_dot is a component with VoltagePointMacroMixin

                # Create point and macro together (recommended)
                quantum_dot.add_point_with_ramp_macro(
                    'load',
                    voltages={'virtual_dot_0': 0.3},
                    hold_duration=200,
                    ramp_duration=500
                )

                # Execute the macro: ramps over 500ns, holds for 200ns
                quantum_dot.macros['load']()

                # Use in a sequence
                seq = SequenceMacro(name='init', macro_refs=())
                seq = seq.with_macro(quantum_dot, 'load')
                seq(quantum_dot)
        """
        # Create the voltage point
        full_name = self.add_point(
            point_name=macro_name,
            voltages=voltages,
            duration=point_duration,
            replace_existing_point=replace_existing_point,
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

        # # Set parent for proper reference resolution
        # if hasattr(macro, "parent"):
        #     macro.parent = None
        #     macro.parent = self

        return macro

    def with_step_point(
        self,
        name: str,
        voltages: Dict[str, float],
        hold_duration: int = 100,
        point_duration: int = 16,
        replace_existing_point: bool = False,
    ) -> "VoltagePointMacroMixin":
        """
        Fluent API: Add a voltage point with step macro and return self for chaining.

        This is a convenience wrapper around add_point_with_step_macro() that
        returns self to enable method chaining for defining multiple macros.

        Args:
            name: Name for both the point and the macro
            voltages: Voltage values for each gate
            hold_duration: Duration to hold the target voltage (nanoseconds, default: 100)
            point_duration: Default duration stored in VoltageTuningPoint (nanoseconds, default: 16)
            replace_existing_point: If True, overwrites existing point (default: False)

        Returns:
            self: The component instance for method chaining

        Example:
            .. code-block:: python

                # Chain multiple macro definitions
                (component
                    .with_step_point("idle", {"gate": 0.1}, hold_duration=100)
                    .with_step_point("measure", {"gate": 0.2}, hold_duration=200)
                    .with_sequence("init", ["idle", "measure"]))

                # Use in QUA program
                with program() as prog:
                    component.idle()
                    component.measure()
                    component.init()
        """
        self._add_point_with_step_macro(
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
        voltages: Dict[str, float],
        hold_duration: int = 100,
        ramp_duration: int = 16,
        point_duration: int = 16,
        replace_existing_point: bool = False,
    ) -> "VoltagePointMacroMixin":
        """
        Fluent API: Add a voltage point with ramp macro and return self for chaining.

        This is a convenience wrapper around add_point_with_ramp_macro() that
        returns self to enable method chaining for defining multiple macros.

        Args:
            name: Name for both the point and the macro
            voltages: Voltage values for each gate
            hold_duration: Duration to hold the target voltage (nanoseconds, default: 100)
            ramp_duration: Time for gradual voltage transition (nanoseconds, default: 16)
            point_duration: Default duration stored in VoltageTuningPoint (nanoseconds, default: 16)
            replace_existing_point: If True, overwrites existing point (default: False)

        Returns:
            self: The component instance for method chaining

        Example:
            .. code-block:: python

                # Chain multiple macro definitions
                (component
                    .with_ramp_point("load", {"gate": 0.3}, hold_duration=200, ramp_duration=500)
                    .with_step_point("readout", {"gate": 0.15}, hold_duration=1000)
                    .with_sequence("load_and_read", ["load", "readout"]))

                # Use in QUA program
                with program() as prog:
                    component.load()
                    component.readout()
                    component.load_and_read()
        """
        self._add_point_with_ramp_macro(
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
        sequence = SequenceMacro(name=name, description=description).with_macros(
            self, macro_names
        )
        self.macros[name] = sequence

        # Set parent for proper reference resolution (must set to None first per QUAM rules)
        # if hasattr(sequence, "parent"):
        #     sequence.parent = None
        #     sequence.parent = self

        return self
