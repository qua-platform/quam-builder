"""Catalog-based macro registry for quantum-dot components.

This module provides the ``MacroCatalog`` protocol and concrete implementations
for registering and resolving default macro factories per component type.

Architecture
------------
A **catalog** is any object that can provide macro factories for a given
component type.  The ``MacroRegistry`` aggregates catalogs and resolves the
effective factory map for a component instance by merging catalogs in
priority order (lowest first, highest wins per key).

Built-in catalogs:

- ``UtilityMacroCatalog`` (priority 0): ``align`` and ``wait`` for all
  components.
- ``DefaultMacroCatalog`` (priority 100): architecture defaults with
  MRO-based inheritance (internal to this catalog only).

Users supply additional catalogs via ``wire_machine_macros(..., catalogs=[...])``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Dict, Protocol, Type, Union, runtime_checkable

from quam.core.macro import QuamMacro

from quam_builder.tools.macros.default_macros import UTILITY_MACRO_FACTORIES

__all__ = [
    "MacroFactory",
    "MacroFactoryMap",
    "MacroCatalog",
    "MacroRegistry",
    "UtilityMacroCatalog",
    "DefaultMacroCatalog",
    "TypeOverrideCatalog",
    "DISABLED",
]

MacroFactory = Union[Type[QuamMacro], Callable[[], QuamMacro]]
"""A macro class or zero-arg callable that returns a ``QuamMacro`` instance."""

MacroFactoryMap = Dict[str, MacroFactory]
"""Mapping from macro name to factory."""


# ---------------------------------------------------------------------------
# Sentinel for disabling/removing macros
# ---------------------------------------------------------------------------


class _DisabledSentinel:
    """Sentinel indicating a macro should be removed."""

    _instance: _DisabledSentinel | None = None

    def __new__(cls) -> _DisabledSentinel:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "DISABLED"

    def __bool__(self) -> bool:
        return False


DISABLED = _DisabledSentinel()


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MacroCatalog(Protocol):
    """A source of macro factories for component types.

    Implement this protocol in external packages to provide a complete
    or partial set of macro defaults.  Return an empty dict from
    ``get_factories`` for unsupported component types.
    """

    def get_factories(self, component_type: type) -> MacroFactoryMap:
        """Return macro-name -> factory for *component_type*.

        Args:
            component_type: The component class to resolve factories for.

        Returns:
            Dict mapping macro name strings to factories.  Return an
            empty dict for unsupported component types.
        """
        ...

    @property
    def priority(self) -> int:
        """Merge priority.  Higher values override lower.

        Convention: 0 = utility, 100 = architecture defaults,
        200 = lab/external, 300 = instance overrides.
        """
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class MacroRegistry:
    """Aggregates :class:`MacroCatalog` instances and resolves factories."""

    def __init__(self) -> None:
        self._catalogs: list[MacroCatalog] = []

    def register_catalog(self, catalog: MacroCatalog) -> None:
        """Add a catalog.  Catalogs are applied in priority order."""
        self._catalogs.append(catalog)
        self._catalogs.sort(key=lambda c: c.priority)

    def resolve_factories(self, component: object) -> MacroFactoryMap:
        """Resolve effective macro factories for *component*.

        Walks catalogs low-to-high priority; higher priority wins per key.
        """
        resolved: MacroFactoryMap = {}
        for catalog in self._catalogs:
            resolved.update(catalog.get_factories(type(component)))
        return resolved

    @property
    def catalogs(self) -> tuple[MacroCatalog, ...]:
        """Registered catalogs in priority order (read-only)."""
        return tuple(self._catalogs)


# ---------------------------------------------------------------------------
# Built-in catalogs
# ---------------------------------------------------------------------------


class UtilityMacroCatalog:
    """Utility macros (``align``, ``wait``) for all macro-dispatch components.

    Returns the same set of utility factories regardless of
    *component_type*, so every macro-dispatch component gets
    ``align`` and ``wait``.
    """

    priority = 0

    def get_factories(self, component_type: type) -> MacroFactoryMap:
        """Return utility macro factories (same for every component type)."""
        return dict(UTILITY_MACRO_FACTORIES)


class DefaultMacroCatalog:
    """Built-in macro defaults for quantum-dot component types.

    Handles MRO-based inheritance internally: ``LDQubit`` inherits
    ``QuantumDot`` defaults, but types marked *authoritative* (e.g.
    ``SensorDot``) reset the inherited map.
    """

    priority = 100

    def __init__(self) -> None:
        self._type_factories: dict[type, MacroFactoryMap] = {}
        self._authoritative_types: set[type] = set()
        self._register_defaults()

    # -- public registration API (also used by _register_defaults) ----------

    def register(
        self,
        component_type: type,
        factories: Mapping[str, MacroFactory],
        *,
        authoritative: bool = False,
    ) -> None:
        """Register macro factories for *component_type*.

        Args:
            component_type: The component class.
            factories: Macro-name -> factory mapping.
            authoritative: If ``True``, MRO resolution resets the
                accumulated map when it reaches this type (i.e. the
                type does **not** inherit defaults from its bases).
        """
        self._type_factories[component_type] = dict(factories)
        if authoritative:
            self._authoritative_types.add(component_type)

    # -- protocol implementation --------------------------------------------

    def get_factories(self, component_type: type) -> MacroFactoryMap:
        """Resolve factories by walking the MRO (base -> derived).

        Args:
            component_type: The component class to resolve factories for.

        Returns:
            Merged factory map accumulated across the MRO, with
            authoritative types resetting the accumulator.
        """
        resolved: MacroFactoryMap = {}
        for ancestor in reversed(component_type.mro()):
            if ancestor in self._type_factories:
                if ancestor in self._authoritative_types:
                    resolved = dict(self._type_factories[ancestor])
                else:
                    resolved.update(self._type_factories[ancestor])
        return resolved

    # -- built-in defaults --------------------------------------------------

    def _register_defaults(self) -> None:
        from quam_builder.architecture.quantum_dots.components import QPU
        from quam_builder.architecture.quantum_dots.components.quantum_dot import (
            QuantumDot,
        )
        from quam_builder.architecture.quantum_dots.components.quantum_dot_pair import (
            QuantumDotPair,
        )
        from quam_builder.architecture.quantum_dots.components.sensor_dot import (
            SensorDot,
        )
        from quam_builder.architecture.quantum_dots.operations.default_macros import (
            QPU_STATE_MACROS,
            SINGLE_QUBIT_MACROS,
            STATE_POINT_MACROS,
            TWO_QUBIT_MACROS,
        )
        from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
            MeasurePSBPairMacro,
            SensorDotMeasureMacro,
        )
        from quam_builder.architecture.quantum_dots.operations.names import (
            VoltagePointName,
        )
        from quam_builder.architecture.quantum_dots.qubit import LDQubit
        from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair

        self.register(QPU, QPU_STATE_MACROS)
        self.register(LDQubit, SINGLE_QUBIT_MACROS)
        self.register(LDQubitPair, TWO_QUBIT_MACROS)
        self.register(QuantumDot, STATE_POINT_MACROS)
        self.register(
            QuantumDotPair,
            {**STATE_POINT_MACROS, VoltagePointName.MEASURE: MeasurePSBPairMacro},
        )
        self.register(
            SensorDot,
            {VoltagePointName.MEASURE: SensorDotMeasureMacro},
            authoritative=True,
        )


class TypeOverrideCatalog:
    """Ad-hoc type-level overrides without a full catalog class.

    Example::

        wire_machine_macros(
            machine,
            catalogs=[
                TypeOverrideCatalog({
                    LDQubit: {SingleQubitMacroName.INITIALIZE: LabInitMacro},
                }),
            ],
        )
    """

    priority = 200

    def __init__(self, overrides: Mapping[type, Mapping[str, MacroFactory]]) -> None:
        """Create a type-override catalog.

        Args:
            overrides: Mapping from component class to macro-name -> factory.
                Only exact type matches are used (no MRO walk).
        """
        self._overrides: dict[type, MacroFactoryMap] = {t: dict(m) for t, m in overrides.items()}

    def get_factories(self, component_type: type) -> MacroFactoryMap:
        """Return overrides for *component_type*, or empty dict if none."""
        return dict(self._overrides.get(component_type, {}))
