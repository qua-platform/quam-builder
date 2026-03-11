"""Macro dispatch mixin with compiled-call caching and sticky-voltage tracking."""

from __future__ import annotations

import math
import warnings
import weakref
from numbers import Real
from typing import Callable, Dict, Set, Tuple

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
_WARNED_MACRO_KEYS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# Runtime-only caches keyed by component instance (never serialized).


@quam_dataclass
class MacroDispatchMixin(QuantumComponent):
    """Mixin for macro storage, compiled dispatch, and runtime tracking."""

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

    def _warned_macro_keys(self) -> Set[Tuple[str, str]]:
        """Return per-instance set of macro warning keys already emitted."""
        keys = _WARNED_MACRO_KEYS.get(self)
        if keys is None:
            keys = set()
            _WARNED_MACRO_KEYS[self] = keys
        return keys

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
        """Compile a callable wrapper that preserves sticky tracking behavior."""

        def _call(**kwargs):
            return self._execute_macro_with_sticky_tracking(macro, **kwargs)

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

    def _macro_warning_key(self, macro: QuamMacro) -> Tuple[str, str]:
        """Build a stable key used to suppress duplicate warning messages."""
        macro_class_name = type(macro).__name__
        try:
            macro_id = str(getattr(macro, "inferred_id", getattr(macro, "id", macro_class_name)))
        except Exception:  # pragma: no cover - defensive fallback
            macro_id = macro_class_name
        return macro_class_name, macro_id

    def _warn_once_missing_macro_duration(self, macro: QuamMacro, reason: str) -> None:
        key = self._macro_warning_key(macro)
        warned_keys = self._warned_macro_keys()
        if key in warned_keys:
            return
        warned_keys.add(key)
        warnings.warn(
            (
                "Skipping sticky-voltage tracking for macro "
                f"'{key[1]}' ({key[0]}): {reason}. "
                "Define `inferred_duration` in seconds for non-voltage macros."
            ),
            stacklevel=3,
        )

    def _duration_ns_for_sticky_tracking(self, macro: QuamMacro) -> int | None:
        """Resolve macro duration to 4 ns-quantized nanoseconds for tracking."""
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

        quantized_duration_ns = int(round(duration_seconds_f * 1e9 / 4.0)) * 4
        return max(quantized_duration_ns, 0)

    def _execute_macro_with_sticky_tracking(self, macro: QuamMacro, **kwargs):
        """Execute macro and update sticky-voltage integral when needed."""
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
        """Resolve macro name-or-reference into canonical reference string."""
        if name_or_ref.startswith("#"):
            return name_or_ref
        if name_or_ref not in self.macros:
            raise KeyError(
                f"{description} '{name_or_ref}' not found in macros. "
                f"Available macros: {list(self.macros.keys())}"
            )
        return f"#../{name_or_ref}"
