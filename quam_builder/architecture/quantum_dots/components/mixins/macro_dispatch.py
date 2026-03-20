"""Macro dispatch mixin for quantum-dot components.

Provides the ``MacroDispatchMixin`` base class that gives any quantum-dot
component automatic macro storage, default materialization from the
:mod:`~quam_builder.architecture.quantum_dots.operations.macro_registry`,
and attribute-based macro invocation.

Macro execution goes directly through ``macro.apply(**kwargs)`` without
any additional tracking or wrapping.
"""

from __future__ import annotations

import warnings
from typing import Dict

from dataclasses import field

from quam.components import QuantumComponent
from quam.core import quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.operations.component_macro_catalog import (
    register_default_component_macro_factories,
)
from quam_builder.architecture.quantum_dots.operations.macro_registry import (
    get_default_macro_factories,
)

__all__ = ["MacroDispatchMixin"]


@quam_dataclass
class MacroDispatchMixin(QuantumComponent):
    """Mixin for macro storage and dispatch.

    Any component that inherits from this mixin gains:

    * A ``macros`` dict populated with architecture defaults on construction.
    * Attribute-based macro invocation (``component.x180()`` dispatches to
      ``component.macros["x180"].apply()``).

    Example::

        qubit = machine.qubits["q1"]
        qubit.x180()                     # attribute dispatch
        qubit.macros["x180"].apply()     # direct access
    """

    macros: Dict[str, QuamMacro] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize macro storage, defaults, and parent links."""
        self._ensure_macros_dict()
        self.ensure_default_macros()
        self._ensure_macro_parents()

    def _ensure_macros_dict(self) -> None:
        """Ensure ``self.macros`` exists before default materialization."""
        if getattr(self, "macros", None) is None:
            self.macros = {}

    def ensure_default_macros(self) -> None:
        """Materialize default macro instances for this component type."""
        register_default_component_macro_factories()
        for macro_name, macro_class in get_default_macro_factories(self).items():
            if macro_name not in self.macros:
                self.macros[macro_name] = macro_class()

    def _ensure_macro_parents(self) -> None:
        """Ensure all macros have their parent set to this component."""
        for macro in self.macros.values():
            if getattr(macro, "parent", None) is None:
                macro.parent = self

    def set_macro(self, name: str, macro: QuamMacro) -> None:
        """Add or replace a macro."""
        self.macros[name] = macro
        if getattr(macro, "parent", None) is None:
            macro.parent = self

    def __getattr__(self, name):
        """Expose macros as callable methods via attribute access."""
        if name in self.macros:
            macro = self.macros[name]
            if getattr(macro, "parent", None) is None:
                warnings.warn(
                    f"Macro '{name}' on {type(self).__name__} has no parent set. "
                    f"This may indicate it was added without using set_macro().",
                    stacklevel=2,
                )
                macro.parent = self
            return macro.apply
        raise AttributeError(f"'{type(self).__name__}' object has no attribute or macro '{name}'")

    def _resolve_macro_ref(self, name_or_ref: str, description: str) -> str:
        """Resolve macro name-or-reference into canonical reference string."""
        if name_or_ref.startswith("#"):
            return name_or_ref
        if name_or_ref not in self.macros:
            raise KeyError(
                f"{description} '{name_or_ref}' not found in macros. "
                f"Available macros: {list(self.macros.keys())}"
            )
        return f"#../{name_or_ref}"
