"""Macro dispatch mixin for dynamic macro invocation.

This module provides the infrastructure for storing and dynamically
accessing macros as methods.
"""

import math
import warnings
from numbers import Real
from typing import Dict, Set, Tuple

from dataclasses import field

from quam.core import quam_dataclass
from quam.core.macro import QuamMacro
from quam.components import QuantumComponent

from quam_builder.tools.macros.default_macros import DEFAULT_MACROS

__all__ = ["MacroDispatchMixin"]


@quam_dataclass
class MacroDispatchMixin(QuantumComponent):
    """Mixin providing macro storage and dynamic dispatch infrastructure.

    This mixin enables components to:
    - Store macros in a serializable dictionary
    - Access macros as methods via __getattr__
    - Automatically initialize default macros

    Features:
        - Dynamic macro access: Macros in self.macros are callable as methods
        - Serializable: All state stored in self.macros dict, compatible with QuAM serialization

    Example:
        component.macros['idle'] = StepPointMacro(...)
        component.idle()  # Calls the macro via __getattr__
    """

    macros: Dict[str, QuamMacro] = field(default_factory=dict)
    _sticky_tracking_warned_macros: Set[Tuple[str, str]] = field(
        default_factory=set, init=False, repr=False, metadata={"exclude": True}
    )

    def __post_init__(self):
        """Initialize macro containers and set parent links."""
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
        """Enable calling macros as methods via attribute access.

        This allows dynamically-registered macros to be called as if they were
        methods decorated with @QuantumComponent.register_macro, providing a
        cleaner API: component.my_macro() instead of component.macros['my_macro']()

        Example:
            component.macros['idle'] = StepPointMacro(...)
            component.idle()  # Calls the macro via __getattr__
        """
        # __getattr__ is only called after normal attribute lookup fails,
        # so we only need to check macros here
        macros = self.__dict__.get("macros", {})
        if name in macros:
            macro = macros[name]
            return lambda **kwargs: self._execute_macro_with_sticky_tracking(macro, **kwargs)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute or macro '{name}'")

    def _macro_warning_key(self, macro: QuamMacro) -> Tuple[str, str]:
        """Create a stable warning key for one-time macro warnings."""
        macro_class_name = type(macro).__name__
        try:
            macro_id = str(getattr(macro, "inferred_id", getattr(macro, "id", macro_class_name)))
        except Exception:  # pragma: no cover - defensive fallback
            macro_id = macro_class_name
        return macro_class_name, macro_id

    def _warn_once_missing_macro_duration(self, macro: QuamMacro, reason: str) -> None:
        """Warn once per macro id/class when sticky tracking duration is unavailable."""
        key = self._macro_warning_key(macro)
        if key in self._sticky_tracking_warned_macros:
            return
        self._sticky_tracking_warned_macros.add(key)
        warnings.warn(
            (
                "Skipping sticky-voltage tracking for macro "
                f"'{key[1]}' ({key[0]}): {reason}. "
                "Define `inferred_duration` in seconds for non-voltage macros."
            ),
            stacklevel=3,
        )

    def _duration_ns_for_sticky_tracking(self, macro: QuamMacro) -> int | None:
        """Resolve macro inferred duration (seconds) to quantized nanoseconds."""
        duration_seconds = getattr(macro, "inferred_duration", None)
        if duration_seconds is None:
            self._warn_once_missing_macro_duration(
                macro, "missing or unresolved `inferred_duration`"
            )
            return None
        if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, Real):
            self._warn_once_missing_macro_duration(
                macro, f"non-numeric `inferred_duration` value '{duration_seconds}'"
            )
            return None

        duration_seconds_f = float(duration_seconds)
        if not math.isfinite(duration_seconds_f) or duration_seconds_f < 0:
            self._warn_once_missing_macro_duration(
                macro, f"invalid `inferred_duration` value '{duration_seconds}'"
            )
            return None

        # Convert seconds -> ns and quantize to OPX clock-cycle boundaries.
        quantized_duration_ns = int(round(duration_seconds_f * 1e9 / 4.0)) * 4
        return max(quantized_duration_ns, 0)

    def _execute_macro_with_sticky_tracking(self, macro: QuamMacro, **kwargs):
        """Execute a macro and account for sticky voltage hold time when needed."""
        result = macro.apply(**kwargs)

        if getattr(macro, "updates_voltage_tracking", False):
            return result

        duration_ns = self._duration_ns_for_sticky_tracking(macro)
        if duration_ns in (None, 0):
            return result

        voltage_sequence = getattr(self, "voltage_sequence", None)
        track_fn = getattr(voltage_sequence, "track_sticky_duration", None)
        if callable(track_fn):
            track_fn(duration_ns)

        return result

    def _resolve_macro_ref(self, name_or_ref: str, description: str) -> str:
        """Convert macro name to reference string, validating existence.

        Args:
            name_or_ref: Either a macro name (e.g., 'measure') or reference string (starts with '#')
            description: Description for error messages (e.g., 'Measurement macro')

        Returns:
            str: Reference string to the macro

        Raises:
            KeyError: If name_or_ref is a macro name that doesn't exist in self.macros
        """
        if name_or_ref.startswith("#"):
            return name_or_ref
        if name_or_ref not in self.macros:
            raise KeyError(
                f"{description} '{name_or_ref}' not found in macros. "
                f"Available macros: {list(self.macros.keys())}"
            )
        return f"#../{name_or_ref}"
