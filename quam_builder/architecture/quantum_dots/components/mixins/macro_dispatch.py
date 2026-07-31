"""Macro dispatch mixin for quantum-dot components.

Provides the ``MacroDispatchMixin`` base class that gives any quantum-dot
component automatic macro storage, default materialization from the
:mod:`~quam_builder.architecture.quantum_dots.operations.macro_catalog`,
and attribute-based macro invocation.

Macro execution goes directly through ``macro.apply(**kwargs)`` without
any additional tracking or wrapping.
"""

from __future__ import annotations

import warnings
from typing import Any, Dict

from dataclasses import field

from quam.components import QuantumComponent
from quam.core import quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.operations.macro_catalog import (
    DefaultMacroCatalog,
    MacroRegistry,
    UtilityMacroCatalog,
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

    def __post_init__(self) -> None:
        """Initialize macro storage, defaults, and parent links."""
        super().__post_init__()
        self._ensure_macros_dict()
        self.ensure_default_macros()
        self._ensure_macro_parents()

    def _ensure_macros_dict(self) -> None:
        """Ensure ``self.macros`` exists before default materialization."""
        if getattr(self, "macros", None) is None:
            self.macros = {}

    def ensure_default_macros(self) -> None:
        """Materialize default macro instances for this component type."""
        registry = MacroRegistry()
        registry.register_catalog(UtilityMacroCatalog())
        registry.register_catalog(DefaultMacroCatalog())
        for macro_name, factory in registry.resolve_factories(self).items():
            if macro_name not in self.macros:
                self.macros[macro_name] = factory()

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

    def __getattr__(self, name: str) -> Any:
        """Expose macros via attribute access.

        Returns the macro object itself when callable (has ``__call__``),
        enabling both ``component.x()`` and ``component.x.update()``.
        Falls back to returning ``macro.apply`` for macros that are not
        directly callable.
        """
        if name in self.macros:
            macro = self.macros[name]
            if getattr(macro, "parent", None) is None:
                warnings.warn(
                    f"Macro '{name}' on {type(self).__name__} has no parent set. "
                    f"This may indicate it was added without using set_macro().",
                    stacklevel=2,
                )
                macro.parent = self
            if callable(macro):
                return macro
            return macro.apply
        raise AttributeError(f"'{type(self).__name__}' object has no attribute or macro '{name}'")
