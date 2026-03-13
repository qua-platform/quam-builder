"""Macro and pulse wiring with user override utilities for quantum-dot machines.

This module is the runtime entry point for:
1. Materializing component defaults from the component-type registry.
2. Applying user overrides from a TOML profile and/or Python mapping.
3. Supporting partial overrides while retaining all untouched defaults.
4. Wiring default pulses onto qubit XY drives and sensor dot resonators.
"""

from __future__ import annotations

from collections.abc import Mapping
import importlib
from pathlib import Path
from typing import Any
import tomllib

from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.operations.macro_registry import (
    get_default_macro_factories,
)
from quam_builder.architecture.quantum_dots.operations.component_macro_catalog import (
    register_default_component_macro_factories,
)
from quam_builder.architecture.quantum_dots.operations.component_pulse_catalog import (
    register_default_component_pulse_factories,
    _make_xy_pulse_factories,
    _make_readout_pulse,
)

__all__ = [
    "wire_machine_macros",
    "load_macro_profile",
]


def load_macro_profile(profile_path: str | Path | None) -> dict[str, Any]:
    """Load an optional TOML macro profile.

    Args:
        profile_path: Path to a TOML file, or ``None`` to skip profile loading.

    Returns:
        Decoded profile data as a mapping.

    Raises:
        FileNotFoundError: If the path is provided and does not exist.
        ValueError: If the parsed file is not a dictionary-like structure.
    """
    if profile_path is None:
        return {}
    path = Path(profile_path)
    if not path.exists():
        raise FileNotFoundError(f"Macro profile not found: {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        raise ValueError("Macro profile must decode to a dictionary.")
    return data


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` onto ``base`` and return a new mapping."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def _iter_macro_components(machine: Any):
    """Iterate components on a machine that expose a ``macros`` mapping.

    Yields:
        Tuples of ``(<component_path>, <component_instance>)`` where
        ``component_path`` is suitable for ``instances.<path>`` overrides.
    """
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


def _resolve_macro_factory(factory_spec: Any):
    """Resolve macro factory spec to a concrete ``QuamMacro`` subclass.

    Args:
        factory_spec: Either a class object or a ``module.path:Symbol`` string.

    Returns:
        A ``QuamMacro`` subclass.
    """
    if isinstance(factory_spec, str):
        if ":" not in factory_spec:
            raise ValueError(
                f"Macro factory '{factory_spec}' must use 'module.path:SymbolName' format."
            )
        module_name, symbol_name = factory_spec.split(":", 1)
        module = importlib.import_module(module_name)
        factory = getattr(module, symbol_name)
    else:
        factory = factory_spec

    if not isinstance(factory, type) or not issubclass(factory, QuamMacro):
        raise TypeError(
            f"Resolved macro factory '{factory}' must be a QuamMacro subclass, "
            f"got '{type(factory).__name__}'."
        )
    return factory


def _set_component_macro(component: Any, name: str, macro: QuamMacro) -> None:
    """Set or replace a macro on a component while keeping parent links valid."""
    set_macro = getattr(component, "set_macro", None)
    if callable(set_macro):
        set_macro(name, macro)
        return

    if not hasattr(component, "macros") or component.macros is None:
        component.macros = {}
    component.macros[name] = macro
    if getattr(macro, "parent", None) is None:
        macro.parent = component


def _remove_component_macro(component: Any, name: str, strict: bool) -> None:
    """Remove a macro from a component and invalidate dispatch cache if needed."""
    macros = getattr(component, "macros", None)
    if not isinstance(macros, Mapping):
        if strict:
            raise KeyError(f"Component '{component}' has no macros container.")
        return
    if name not in macros:
        if strict:
            raise KeyError(f"Macro '{name}' not found on component '{component.id}'.")
        return
    del macros[name]
    invalidate = getattr(component, "_invalidate_macro_dispatch", None)
    if callable(invalidate):
        invalidate(name)


def _normalize_macro_override(entry: Any) -> tuple[type[QuamMacro] | None, dict[str, Any], bool]:
    """Normalize one macro override entry into factory/params/enabled tuple."""
    if isinstance(entry, str) or (isinstance(entry, type) and issubclass(entry, QuamMacro)):
        return _resolve_macro_factory(entry), {}, True

    if not isinstance(entry, Mapping):
        raise TypeError(
            "Macro override entry must be a mapping, a QuamMacro class, or import path string."
        )

    enabled = bool(entry.get("enabled", True))
    if not enabled:
        return None, {}, False

    factory_spec = entry.get("factory")
    if factory_spec is None:
        raise ValueError("Enabled macro override must provide 'factory'.")
    params = entry.get("params", {})
    if not isinstance(params, Mapping):
        raise TypeError("Macro override 'params' must be a mapping.")
    return _resolve_macro_factory(factory_spec), dict(params), True


def _apply_macros_to_component(
    component: Any,
    macros_config: Mapping[str, Any],
    *,
    strict: bool,
    context: str,
) -> None:
    """Apply normalized macro override entries to one component."""
    known_macros = set(get_default_macro_factories(component).keys())
    known_macros.update(getattr(component, "macros", {}).keys())

    for macro_name, entry in macros_config.items():
        if strict and macro_name not in known_macros:
            raise KeyError(
                f"[{context}] Unknown macro '{macro_name}' for component "
                f"{type(component).__name__}({getattr(component, 'id', '?')}). "
                f"Known macros: {sorted(known_macros)}"
            )

        factory, params, enabled = _normalize_macro_override(entry)
        if not enabled:
            _remove_component_macro(component, macro_name, strict=strict)
            continue

        macro = factory(**params)  # type: ignore[misc]
        _set_component_macro(component, macro_name, macro)


def _ensure_default_pulses(machine: Any) -> None:
    """Materialize default pulses onto qubit XY drives and sensor dot resonators.

    Called automatically at the end of :func:`wire_machine_macros`, after macro
    wiring is complete.  Pulse wiring is additive: only pulse names not already
    present in a channel's ``operations`` dict are added.  User-supplied or
    override-supplied pulses always take precedence.

    Qubit XY drives:
        For each qubit in ``machine.qubits`` that has an ``xy`` drive with an
        ``operations`` dict, adds a single ``GaussianPulse`` reference pulse
        named ``"gaussian"``.  The ``XYDriveMacro`` scales amplitude for
        rotation angle and applies virtual-Z for rotation axis, so only one
        calibrated pulse is needed.  The pulse is drive-type aware: IQ/MW
        channels get ``axis_angle=0.0``; ``SingleChannel`` uses ``axis_angle=None``.

    Sensor dot readout resonators:
        For each sensor dot in ``machine.sensor_dots`` that has a
        ``readout_resonator`` with an ``operations`` dict, adds a default
        ``SquareReadoutPulse`` named ``"readout"``.

    Args:
        machine: Target machine object with ``qubits`` and/or ``sensor_dots``
            collections.
    """
    register_default_component_pulse_factories()

    qubits = getattr(machine, "qubits", None)
    if isinstance(qubits, Mapping):
        for qubit in qubits.values():
            xy = getattr(qubit, "xy", None)
            if xy is None:
                continue
            operations = getattr(xy, "operations", None)
            if operations is None:
                continue
            default_pulses = _make_xy_pulse_factories(xy)
            for pulse_name, pulse in default_pulses.items():
                if pulse_name not in operations:
                    operations[pulse_name] = pulse

    sensor_dots = getattr(machine, "sensor_dots", None)
    if isinstance(sensor_dots, Mapping):
        for sensor_dot in sensor_dots.values():
            resonator = getattr(sensor_dot, "readout_resonator", None)
            if resonator is None:
                continue
            operations = getattr(resonator, "operations", None)
            if operations is None:
                continue
            if "readout" not in operations:
                operations["readout"] = _make_readout_pulse()


def _apply_pulse_overrides(
    machine: Any,
    merged_overrides: Mapping[str, Any],
) -> None:
    """Apply pulse overrides from a TOML profile or runtime mapping.

    Called automatically at the end of :func:`wire_machine_macros`, after
    ``_ensure_default_pulses`` has materialized defaults.

    Override schema (inside both ``component_types`` and ``instances`` scopes)::

        [component_types.LDQubit.pulses]
        x180 = {type = "GaussianPulse", length = 500, amplitude = 0.3, sigma = 83}

        [instances."qubits.q1".pulses]
        x180 = {type = "GaussianPulse", length = 800, amplitude = 0.15, sigma = 133}

    Supported pulse types: ``GaussianPulse``, ``SquarePulse``,
    ``SquareReadoutPulse``, ``DragPulse`` (if available in the quam version).

    To remove a pulse, set ``enabled = false``::

        [instances."qubits.q1".pulses]
        "-y90" = {enabled = false}

    Precedence (last wins):
        1. Default pulses from ``_ensure_default_pulses``
        2. Type-level overrides (``component_types.<TypeName>.pulses``)
        3. Instance-level overrides (``instances.<path>.pulses``)

    Args:
        machine: Target machine whose component pulses should be overridden.
        merged_overrides: Combined TOML profile + runtime override mapping,
            as produced by ``_deep_merge(profile_data, macro_overrides)``.
    """
    from quam.components import pulses as quam_pulses

    _PULSE_TYPE_MAP = {
        "GaussianPulse": quam_pulses.GaussianPulse,
        "SquarePulse": quam_pulses.SquarePulse,
        "SquareReadoutPulse": quam_pulses.SquareReadoutPulse,
    }
    if hasattr(quam_pulses, "DragPulse"):
        _PULSE_TYPE_MAP["DragPulse"] = quam_pulses.DragPulse

    def _apply_pulse_config_to_operations(operations: dict, pulses_config: Mapping, context: str):
        for pulse_name, entry in pulses_config.items():
            if not isinstance(entry, Mapping):
                continue
            enabled = entry.get("enabled", True)
            if not enabled:
                operations.pop(pulse_name, None)
                continue
            pulse_type_name = entry.get("type")
            if pulse_type_name is None:
                continue
            pulse_cls = _PULSE_TYPE_MAP.get(pulse_type_name)
            if pulse_cls is None:
                raise ValueError(
                    f"[{context}] Unknown pulse type '{pulse_type_name}'. "
                    f"Known types: {sorted(_PULSE_TYPE_MAP)}"
                )
            params = {k: v for k, v in entry.items() if k not in ("type", "enabled")}
            operations[pulse_name] = pulse_cls(**params)

    def _get_pulse_target_operations(component: Any) -> dict | None:
        """Find operations dict on a component's drive or resonator."""
        xy = getattr(component, "xy", None)
        if xy is not None:
            return getattr(xy, "operations", None)
        rr = getattr(component, "readout_resonator", None)
        if rr is not None:
            return getattr(rr, "operations", None)
        return getattr(component, "operations", None)

    components_by_path = dict(_iter_macro_components(machine))

    type_overrides = merged_overrides.get("component_types", {})
    if isinstance(type_overrides, Mapping):
        for _, component in components_by_path.items():
            for type_key in (
                type(component).__name__,
                f"{type(component).__module__}.{type(component).__qualname__}",
            ):
                type_config = type_overrides.get(type_key)
                if type_config is None:
                    continue
                pulses_config = type_config.get("pulses", {})
                if not isinstance(pulses_config, Mapping) or not pulses_config:
                    continue
                operations = _get_pulse_target_operations(component)
                if operations is not None:
                    _apply_pulse_config_to_operations(
                        operations, pulses_config, f"component_types.{type_key}"
                    )

    instance_overrides = merged_overrides.get("instances", {})
    if isinstance(instance_overrides, Mapping):
        for component_path, component_config in instance_overrides.items():
            if component_path not in components_by_path:
                continue
            pulses_config = component_config.get("pulses", {})
            if not isinstance(pulses_config, Mapping) or not pulses_config:
                continue
            component = components_by_path[component_path]
            operations = _get_pulse_target_operations(component)
            if operations is not None:
                _apply_pulse_config_to_operations(
                    operations, pulses_config, f"instances.{component_path}"
                )


def wire_machine_macros(
    machine: Any,
    *,
    macro_profile_path: str | Path | None = None,
    macro_overrides: Mapping[str, Any] | None = None,
    strict: bool = True,
) -> None:
    """Wire defaults and user-configured macro/pulse overrides onto machine components.

    Override schema (merged in this order: profile first, then runtime overrides):

    - component_types.<TypeName>.macros.<macro_name> = {factory, params?, enabled?}
    - instances.<collection.id>.macros.<macro_name> = {factory, params?, enabled?}
    - component_types.<TypeName>.pulses.<pulse_name> = {type, ...params}
    - instances.<collection.id>.pulses.<pulse_name> = {type, ...params}

    Args:
        machine: Target machine whose components should be wired.
        macro_profile_path: Optional TOML file path.
        macro_overrides: Optional runtime override mapping.
        strict: If True, unknown paths/macros raise explicit errors.
    """

    register_default_component_macro_factories()
    profile_data = load_macro_profile(macro_profile_path)
    merged_overrides = _deep_merge(profile_data, macro_overrides or {})

    components_by_path = dict(_iter_macro_components(machine))

    # Ensure defaults are materialized before applying overrides.
    for component in components_by_path.values():
        ensure_defaults = getattr(component, "ensure_default_macros", None)
        if callable(ensure_defaults):
            ensure_defaults()

    type_overrides = merged_overrides.get("component_types", {})
    if type_overrides:
        if not isinstance(type_overrides, Mapping):
            raise TypeError("'component_types' overrides must be a mapping.")
        for _, component in components_by_path.items():
            for type_key in (
                type(component).__name__,
                f"{type(component).__module__}.{type(component).__qualname__}",
            ):
                type_config = type_overrides.get(type_key)
                if type_config is None:
                    continue
                macros_config = type_config.get("macros", {})
                if not isinstance(macros_config, Mapping):
                    raise TypeError(f"component_types.{type_key}.macros must be a mapping.")
                _apply_macros_to_component(
                    component,
                    macros_config,
                    strict=strict,
                    context=f"component_types.{type_key}",
                )

    instance_overrides = merged_overrides.get("instances", {})
    if instance_overrides:
        if not isinstance(instance_overrides, Mapping):
            raise TypeError("'instances' overrides must be a mapping.")
        for component_path, component_config in instance_overrides.items():
            if component_path not in components_by_path:
                if strict:
                    raise KeyError(
                        f"Unknown component path '{component_path}' in macro overrides. "
                        f"Known paths: {sorted(components_by_path)}"
                    )
                continue
            macros_config = component_config.get("macros", {})
            if not isinstance(macros_config, Mapping):
                raise TypeError(f"instances.{component_path}.macros must be a mapping.")
            _apply_macros_to_component(
                components_by_path[component_path],
                macros_config,
                strict=strict,
                context=f"instances.{component_path}",
            )

    # Wire default pulses and apply pulse overrides.
    _ensure_default_pulses(machine)
    _apply_pulse_overrides(machine, merged_overrides)
