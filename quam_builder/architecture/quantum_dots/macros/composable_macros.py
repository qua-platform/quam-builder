"""Composable macros for building complex quantum operation sequences."""

from dataclasses import field
from typing import List, Optional

from qm import qua
from quam import QuamComponent
from quam.core import quam_dataclass
from quam.core.macro.quam_macro import QuamMacro
from quam.core.operation.operations_registry import OperationsRegistry
from quam.utils import string_reference
from quam.utils.exceptions import InvalidReferenceError

__all__ = [
    "SequenceMacro",
    "ConditionalMacro",
]


@quam_dataclass
class ConditionalMacro(QuamMacro):
    """Macro for conditional execution based on measurement outcome.

    Performs: measurement → optional alignment → conditional operation.
    Useful for active reset, state preparation, and conditional operations.

    Attributes:
        measurement_macro: Reference to measurement macro (must return boolean QUA variable)
        conditional_macro: Reference to macro applied conditionally
        invert_condition: If False, apply when measurement is True; if True, apply when False
    """

    measurement_macro: str
    conditional_macro: str
    invert_condition: bool = False

    def __call__(self, **overrides):
        """Invoke macro as callable (QUAM convention).

        Args:
            **overrides: Optional parameter overrides

        Returns:
            Measured state
        """
        if not hasattr(self, "parent") or self.parent is None:
            raise ValueError(
                "Cannot execute macro: macro has no parent. "
                "Ensure macro is attached via component.macros['name'] = macro"
            )
        return self.apply(**overrides)

    def _resolve_macro(self, reference: str) -> QuamMacro:
        """Resolve macro reference to actual macro object.

        Args:
            reference: Reference string to the macro

        Returns:
            Resolved macro

        Raises:
            InvalidReferenceError: If reference cannot be resolved
        """
        try:
            if isinstance(reference, str):
                macro = string_reference.get_referenced_value(
                    self.parent.parent,
                    reference,
                    root=self.parent.parent.get_root(),
                )
            elif isinstance(reference, QuamMacro):
                macro = reference
            else:
                raise InvalidReferenceError(f"Reference type '{reference}' not supported")

        except (InvalidReferenceError, AttributeError) as e:
            raise InvalidReferenceError(f"Could not resolve macro reference '{reference}': {e}")

        if not isinstance(macro, QuamMacro):
            raise TypeError(
                f"Reference '{reference}' resolved to {type(macro).__name__}, expected QuamMacro"
            )

        return macro

    @property
    def inferred_duration(self) -> Optional[float]:
        """Calculate total duration (measurement + conditional macro) in seconds."""
        try:
            measurement = self._resolve_macro(self.measurement_macro)
            conditional = self._resolve_macro(self.conditional_macro)

            measurement_duration = getattr(measurement, "inferred_duration", None)
            conditional_duration = getattr(conditional, "inferred_duration", None)

            if measurement_duration is None or conditional_duration is None:
                return None

            return measurement_duration + conditional_duration
        except (InvalidReferenceError, AttributeError):
            return None

    def apply(self, invert_condition: Optional[bool] = None, **kwargs):
        """Execute conditional operation.

        Args:
            invert_condition: Optional override for condition inversion
            **kwargs: Additional parameters passed to conditional macro

        Returns:
            Measured state
        """
        # Resolve macros
        measurement = self._resolve_macro(self.measurement_macro)
        conditional = self._resolve_macro(self.conditional_macro)

        # Execute measurement
        state = measurement.apply()

        # Apply conditional macro based on condition
        use_inverted = invert_condition if invert_condition is not None else self.invert_condition

        if use_inverted:
            with qua.if_(~state):
                conditional.apply(**kwargs)
        else:
            with qua.if_(state):
                conditional.apply(**kwargs)

        return state


@quam_dataclass
class SequenceMacro(QuamMacro):
    """Macro that executes an ordered list of other macros in sequence.

    Lightweight container preserving serialization by storing macro references.
    Any QuamMacro (PointMacro, PulseMacro, etc.) can participate.

    Attributes:
        name: Sequence name
        macro_refs: Tuple of macro reference strings
        description: Optional description
        return_index: Optional index of macro result to return (default: None returns all)
    """

    name: str
    macro_refs: tuple[str, ...] = field(default_factory=tuple)
    description: Optional[str] = None
    return_index: Optional[int] = None

    def __call__(self, *args, **kwargs):
        """Execute sequence as callable."""
        self.apply(*args, **kwargs)

    def with_reference(self, reference: str) -> "SequenceMacro":
        """Return new SequenceMacro with reference appended.

        Args:
            reference: Macro reference string to append

        Returns:
            New SequenceMacro with updated references
        """
        return SequenceMacro(
            name=self.name,
            macro_refs=self.macro_refs + (reference,),
            description=self.description,
            return_index=self.return_index,
        )

    def with_macro(self, owner: QuamComponent, macro_name: str) -> "SequenceMacro":
        """Append macro by name, creating reference.

        Args:
            owner: Component owning the macro
            macro_name: Name of macro in owner.macros

        Returns:
            New SequenceMacro with macro appended
        """
        reference = self._reference_for(owner, macro_name)
        return self.with_reference(reference)

    def with_macros(self, owner: QuamComponent, macro_names: List[str]) -> "SequenceMacro":
        """Append multiple macros by name.

        Args:
            owner: Component owning the macros
            macro_names: List of macro names

        Returns:
            New SequenceMacro with all macros appended
        """
        sequence = self
        for macro_name in macro_names:
            sequence = sequence.with_macro(owner, macro_name)
        return sequence

    @staticmethod
    def _reference_for(owner: QuamComponent, macro_name: str) -> str:
        """Create or reuse reference for macro name on owner.

        Args:
            owner: Component owning the macro
            macro_name: Macro name

        Returns:
            Reference string

        Raises:
            KeyError: If macro not found
        """
        macros = getattr(owner, "macros", None)
        if macros is None:
            macros = {}
            setattr(owner, "macros", macros)

        if macro_name not in macros:
            raise KeyError(f"Macro '{macro_name}' not found on owner {owner}")

        return f"#./macros/{macro_name}"

    def resolved_macros(self, component: QuamComponent) -> List[QuamMacro]:
        """Resolve stored references to concrete macros.

        Args:
            component: Component from which to resolve references

        Returns:
            List of resolved macros

        Raises:
            InvalidReferenceError: If any reference cannot be resolved
        """
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
        """Execute each referenced macro sequentially.

        Args:
            **kwargs: Parameters passed to each macro

        Returns:
            Result(s) based on return_index setting
        """
        res = []
        for macro in self.resolved_macros(self.parent.parent):
            r = macro.apply(**kwargs)
            res.append(r)

        if self.return_index is not None:
            return res[self.return_index]

    def register_operation(
        self,
        registry: OperationsRegistry,
        operation_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Register this sequence as an operation.

        Args:
            registry: Operations registry
            operation_name: Optional operation name (defaults to self.name)
            description: Optional description
        """
        op_name = operation_name or self.name

        def operation_fn(component: QuamComponent):
            """Execute the sequence via operations registry."""
            sequence = component.sequences[self.name]
            sequence(component)

        operation_fn.__doc__ = description or self.description or f"Execute '{self.name}' sequence."
        operation_fn.__name__ = op_name
        registry.register_operation(op_name)(operation_fn)

    def total_duration_seconds(self, component: QuamComponent) -> Optional[float]:
        """Calculate summed duration of all referenced macros.

        Args:
            component: Component from which to resolve macros

        Returns:
            Total duration in seconds, or None if any duration is unavailable
        """
        durations: List[Optional[float]] = []
        for macro in self.resolved_macros(component):
            duration = getattr(macro, "inferred_duration", None)
            if duration is None:
                duration = getattr(macro, "duration", None)
            durations.append(duration)

        if any(duration is None for duration in durations):
            return None

        return sum(d for d in durations if d is not None)