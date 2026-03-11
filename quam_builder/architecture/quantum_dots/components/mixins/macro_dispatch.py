"""Macro dispatch mixin with compiled-call caching.

Provides the ``MacroDispatchMixin`` base class that gives any quantum-dot
component automatic macro storage, default materialization from the
:mod:`~quam_builder.architecture.quantum_dots.operations.macro_registry`,
and a compiled-dispatch cache for fast ``component.macro_name()`` calls.

The dispatch cache is a per-instance ``WeakKeyDictionary`` that maps
macro names to ``(macro_instance, compiled_callable)`` tuples.  When a
macro is replaced via :meth:`set_macro`, only that entry is invalidated.
The cache is never serialized — it is rebuilt on each ``__post_init__``.

Macro execution goes directly through ``macro.apply(**kwargs)`` without
any additional tracking or wrapping.
"""

from __future__ import annotations

import weakref
from typing import Callable, Dict

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

_DISPATCH_CACHE: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# Runtime-only cache keyed by component instance (never serialized).


@quam_dataclass
class MacroDispatchMixin(QuantumComponent):
    """Mixin for macro storage and compiled dispatch.

    Any component that inherits from this mixin gains:

    * A ``macros`` dict populated with architecture defaults on construction.
    * Attribute-based macro invocation (``component.x180()`` dispatches to
      ``component.macros["x180"].apply()``).
    * A compiled-dispatch cache that avoids repeated lookups.

    Example::

        qubit = machine.qubits["q1"]
        qubit.x180()                     # attribute dispatch
        qubit.call_macro("x180")         # explicit dispatch
        qubit.macros["x180"].apply()     # lowest-level access
    """

    macros: Dict[str, QuamMacro] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize macro storage, defaults, and runtime callable cache."""
        self._ensure_macros_dict()
        self.ensure_default_macros()
        self._rebuild_macro_dispatch()

    def _dispatch_cache(self) -> Dict[str, tuple[QuamMacro, Callable]]:
        """Return per-instance compiled-dispatch cache."""
        cache = _DISPATCH_CACHE.get(self)
        if cache is None:
            cache = {}
            _DISPATCH_CACHE[self] = cache
        return cache

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

    def _compile_macro_callable(self, macro: QuamMacro):
        """Compile a callable wrapper for a macro."""

        def _call(**kwargs):
            return macro.apply(**kwargs)

        return _call

    def _get_compiled_macro_callable(self, macro_name: str) -> Callable:
        """Return cached callable for macro, recompiling when macro instance changes."""
        if macro_name not in self.macros:
            raise KeyError(
                f"Macro '{macro_name}' not found on {type(self).__name__}. "
                f"Available macros: {sorted(self.macros.keys())}"
            )

        macro = self.macros[macro_name]
        cache = self._dispatch_cache()
        cached = cache.get(macro_name)
        if cached is not None and cached[0] is macro:
            return cached[1]

        if getattr(macro, "parent", None) is None:
            macro.parent = self
        compiled = self._compile_macro_callable(macro)
        cache[macro_name] = (macro, compiled)
        return compiled

    def _rebuild_macro_dispatch(self) -> None:
        """Rebuild compiled-call cache from current macro mapping."""
        cache = self._dispatch_cache()
        cache.clear()
        for macro_name, macro in self.macros.items():
            if getattr(macro, "parent", None) is None:
                macro.parent = self
            cache[macro_name] = (macro, self._compile_macro_callable(macro))

    def _invalidate_macro_dispatch(self, macro_name: str) -> None:
        """Invalidate one cached macro callable."""
        self._dispatch_cache().pop(macro_name, None)

    def set_macro(self, name: str, macro: QuamMacro) -> None:
        """Add or replace a macro and keep compiled dispatch in sync."""
        self.macros[name] = macro
        self._invalidate_macro_dispatch(name)

    def call_macro(self, name: str, **kwargs):
        """Execute a macro by name through compiled dispatch."""
        return self._get_compiled_macro_callable(name)(**kwargs)

    def __getattr__(self, name):
        """Expose macros as methods via attribute access."""
        if name in self.macros:
            return self._get_compiled_macro_callable(name)
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
