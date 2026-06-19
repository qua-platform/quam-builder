"""Macro dispatch mixin for dynamic macro invocation.

This module provides the infrastructure for storing and dynamically
accessing macros as methods.
"""

from typing import Dict

from dataclasses import field

from quam.core import quam_dataclass
from quam.core.macro import QuamMacro
from quam.components import QuantumComponent

from quam_builder.architecture.quantum_dots.macros.default_macros import DEFAULT_MACROS

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
            return lambda **kwargs: macro.apply(**kwargs)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute or macro '{name}'")

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
