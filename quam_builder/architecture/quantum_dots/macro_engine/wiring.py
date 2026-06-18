"""Macro and pulse wiring for quantum-dot machines.

This module is the runtime entry point for materializing macro defaults
from the catalog-based registry and applying user overrides.

Public API
----------
- ``wire_machine_macros`` -- top-level function that wires macros **and** pulses.
- ``MacroWirer``   -- materializes macros from a ``MacroRegistry``.
- ``PulseWirer``   -- materializes default pulses onto channels.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Iterable

from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.operations.macro_catalog import (
    DISABLED,
    DefaultMacroCatalog,
    MacroCatalog,
    MacroFactoryMap,
    MacroRegistry,
    UtilityMacroCatalog,
)
from quam_builder.architecture.quantum_dots.operations.pulse_catalog import (
    make_readout_pulse,
    make_xy_pulse_factories,
)

__all__ = [
    "wire_machine_macros",
    "MacroWirer",
    "PulseWirer",
]


# ---------------------------------------------------------------------------
# MacroWirer
# ---------------------------------------------------------------------------


class MacroWirer:
    """Materializes macros onto machine components from a :class:`MacroRegistry`.

    Args:
        registry: The registry to resolve macro factories from.
    """

    def __init__(self, registry: MacroRegistry) -> None:
        self._registry = registry

    def wire(
        self,
        machine: object,
        *,
        instance_overrides: dict[str, MacroFactoryMap] | None = None,
        fill_only: bool = False,
    ) -> None:
        """Materialize defaults and apply overrides for all components.

        Args:
            machine: Target machine whose components should be wired.
            instance_overrides: Per-component-path overrides applied after
                catalog-based defaults.  Keys are paths like ``"qubits.q1"``.
                Use ``DISABLED`` as a factory value to remove a macro.
            fill_only: If ``True``, only add macros that are completely
                absent from a component.  Existing macros (regardless of
                type) are never replaced.  Use during ``load()`` to
                preserve deserialized macro types and calibrated properties.

        Raises:
            KeyError: If an instance override path does not match any
                component, or if ``DISABLED`` targets a non-existent macro.
        """
        components = dict(self._iter_components(machine))

        for component in components.values():
            self._materialize_from_registry(component, fill_only=fill_only)

        if instance_overrides:
            self._apply_instance_overrides(components, instance_overrides)

    # -- internal -----------------------------------------------------------

    def _materialize_from_registry(
        self, component: object, *, fill_only: bool = False
    ) -> None:
        """Materialize macros from the registry onto *component*.

        For each name in the resolved factory map:
        - If the component has no macro for that name, create one.
        - If *fill_only* is ``False`` and the component already has one
          whose type differs from the factory, replace it (catalog
          override during build).
        - If *fill_only* is ``True``, never replace an existing macro
          (preserves deserialized types and calibrated properties during
          load).
        """
        factories = self._registry.resolve_factories(component)
        macros = getattr(component, "macros", None)
        if macros is None:
            return
        for name, factory in factories.items():
            if name not in macros:
                self._set_macro(component, name, factory())
            elif not fill_only and self._factory_overrides_existing(
                factory, macros[name]
            ):
                self._set_macro(component, name, factory())

    @staticmethod
    def _factory_overrides_existing(factory: Any, existing_macro: QuamMacro) -> bool:
        """Return True if *factory* would produce a different macro type or config.

        For bare classes, checks isinstance.  For partials or other
        callables (which carry custom parameters), always replace.
        """
        if isinstance(factory, type):
            return not isinstance(existing_macro, factory)
        # Non-type callable (e.g. functools.partial with custom params) --
        # always treat as an override since we can't compare config.
        return True

    def _apply_instance_overrides(
        self,
        components: dict[str, object],
        overrides: dict[str, MacroFactoryMap],
    ) -> None:
        for path, factory_map in overrides.items():
            if path not in components:
                raise KeyError(
                    f"Unknown component path '{path}'. " f"Known: {sorted(components)}"
                )
            component = components[path]
            for name, factory_or_sentinel in factory_map.items():
                if factory_or_sentinel is DISABLED:
                    self._remove_macro(component, name)
                else:
                    macro = factory_or_sentinel()
                    self._set_macro(component, name, macro)

    @staticmethod
    def _set_macro(component: object, name: str, macro: QuamMacro) -> None:
        set_macro = getattr(component, "set_macro", None)
        if callable(set_macro):
            set_macro(name, macro)
            return
        if not hasattr(component, "macros") or component.macros is None:
            component.macros = {}  # type: ignore[attr-defined]
        component.macros[name] = macro  # type: ignore[attr-defined]
        if getattr(macro, "parent", None) is None:
            macro.parent = component

    @staticmethod
    def _remove_macro(component: object, name: str) -> None:
        macros = getattr(component, "macros", None)
        if not isinstance(macros, Mapping):
            raise KeyError(f"Component '{component}' has no macros container.")
        if name not in macros:
            raise KeyError(
                f"Macro '{name}' not found on "
                f"'{getattr(component, 'id', component)}'."
            )
        del macros[name]

    @staticmethod
    def _iter_components(machine: object) -> Iterable[tuple[str, Any]]:
        """Yield ``(path, component)`` for all macro-capable components."""
        collection_names = (
            "quantum_dots",
            "sensor_dots",
            "barrier_gates",
            "global_gates",
            "quantum_dot_pairs",
            "qubits",
            "qubit_pairs",
        )
        for collection_name in collection_names:
            collection = getattr(machine, collection_name, None)
            if isinstance(collection, Mapping):
                for name, component in collection.items():
                    if hasattr(component, "macros"):
                        yield f"{collection_name}.{name}", component

        qpu = getattr(machine, "qpu", None)
        if qpu is not None and hasattr(qpu, "macros"):
            yield "qpu", qpu


# ---------------------------------------------------------------------------
# PulseWirer
# ---------------------------------------------------------------------------


class PulseWirer:
    """Materializes default pulses onto machine channels.

    Pulse wiring is additive: only pulse names not already present in a
    channel's ``operations`` dict are added.
    """

    def wire(self, machine: object) -> None:
        """Add default pulses where missing.

        Args:
            machine: Target machine whose channels receive default pulses.
        """
        self._wire_xy_pulses(machine)
        self._wire_readout_pulses(machine)

    @staticmethod
    def _wire_xy_pulses(machine: object) -> None:
        qubits = getattr(machine, "qubits", None)
        for qubit in qubits.values():
            if qubit.xy is None:
                continue
            for name, pulse in make_xy_pulse_factories(qubit.xy).items():
                if name not in qubit.xy.operations:
                    qubit.xy.add_pulse(name, pulse)


    @staticmethod
    def _wire_readout_pulses(machine: object) -> None:
        sensor_dots = getattr(machine, "sensor_dots", None)

        # Should give us a sensor : [qd_pairs] mapping allowing us to create per-qd_pair readout pulses
        if sensor_dots is not None:
            sensor_to_qdpair_mapping = {s : [] for s in list(sensor_dots.keys())}
            quantum_dot_pairs = getattr(machine, "quantum_dot_pairs", None)
            if quantum_dot_pairs is not None: 
                for qd_pair_name, qd_pair in quantum_dot_pairs.items(): 
                    sensors_for_qdp = [sen.name for sen in qd_pair.sensor_dots]
                    for s in sensor_dots.keys(): 
                        if s in sensors_for_qdp: 
                            sensor_to_qdpair_mapping[s].append(qd_pair_name)

        if not isinstance(sensor_dots, Mapping):
            return
        for sensor_dot in sensor_dots.values():
            resonator = getattr(sensor_dot, "readout_resonator", None)
            if resonator is None:
                continue
            operations = getattr(resonator, "operations", None)
            if operations is None:
                continue
            if "readout" not in operations:
                operations["readout"] = make_readout_pulse()
            for qd_pair_name in sensor_to_qdpair_mapping[sensor_dot.name]: 
                op_name = f"readout_{qd_pair_name}"
                if op_name not in operations: 
                    operations[op_name] = make_readout_pulse(qd_pair_name)


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def wire_machine_macros(
    machine: object,
    *,
    catalogs: Sequence[MacroCatalog] | None = None,
    instance_overrides: dict[str, MacroFactoryMap] | None = None,
    fill_only: bool = True,
    save: bool = False,
) -> object:
    """Wire macros and pulses onto a machine.

    This is the main user-facing entry point.  It builds a
    :class:`MacroRegistry` from the built-in catalogs plus any
    user-supplied catalogs, materializes defaults, applies overrides,
    and wires default pulses.

    Args:
        machine: Target machine whose components should be wired.
        catalogs: Additional catalogs (e.g. lab packages).  Applied in
            priority order after built-in defaults.
        instance_overrides: Per-component-path overrides applied last.
            Keys are paths like ``"qubits.q1"``.  Values are
            macro-name -> factory dicts (use enum keys from
            :mod:`~quam_builder.architecture.quantum_dots.operations.names`).
            Use the ``DISABLED`` sentinel to remove a macro.
        fill_only: If ``True``, only add macros that are completely
            absent from a component — existing macros are never replaced.
            Use during ``load()`` to preserve deserialized macro types
            and calibrated property values from JSON.

    Raises:
        KeyError: If an instance override path does not match any
            component, or if ``DISABLED`` targets a non-existent macro.

    Example -- defaults only::

        wire_machine_macros(machine)

    Example -- external catalog::

        from my_lab.catalog import LabMacroCatalog

        wire_machine_macros(machine, catalogs=[LabMacroCatalog()])

    Example -- instance override::

        from quam_builder.architecture.quantum_dots.operations.names import (
            SingleQubitMacroName,
        )

        wire_machine_macros(
            machine,
            instance_overrides={
                "qubits.q1": {SingleQubitMacroName.X_180: TunedX180Macro},
            },
        )
    """
    registry = MacroRegistry()
    registry.register_catalog(UtilityMacroCatalog())
    registry.register_catalog(DefaultMacroCatalog())

    if catalogs:
        for catalog in catalogs:
            registry.register_catalog(catalog)

    MacroWirer(registry).wire(
        machine,
        instance_overrides=instance_overrides,
        fill_only=fill_only,
    )
    PulseWirer().wire(machine)

    if save:
        machine.save()
    return machine
