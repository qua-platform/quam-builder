"""Typed helpers for macro and pulse override construction.

These helpers replace raw nested dicts with validated, IDE-friendly calls.
They produce the same internal format consumed by :func:`wire_machine_macros`,
so raw dicts still work for backward compatibility and TOML profiles.

Usage::

    from quam_builder.architecture.quantum_dots.macro_engine.overrides import (
        macro, disabled, pulse, overrides,
    )

    wire_machine_macros(
        machine,
        component_overrides={
            LDQubit: overrides(macros={
                SingleQubitMacroName.INITIALIZE: macro(InitMacro, ramp_duration=64),
            }),
        },
        instance_overrides={
            "qubits.q2": overrides(macros={
                SingleQubitMacroName.INITIALIZE: macro(InitMacro, ramp_duration=96),
                SingleQubitMacroName.X_180: disabled(),
            }),
        },
    )
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from quam.core.macro import QuamMacro

__all__ = [
    "macro",
    "disabled",
    "pulse",
    "overrides",
    "ComponentOverrides",
]


def macro(factory: type[QuamMacro] | str, **params: Any) -> dict[str, Any]:
    """Create a macro override entry with early validation.

    Args:
        factory: A ``QuamMacro`` subclass or ``"module.path:ClassName"`` string.
        **params: Keyword arguments forwarded to the macro constructor or set
            as attributes after construction.

    Returns:
        Override dict in the format expected by :func:`wire_machine_macros`.

    Raises:
        TypeError: If *factory* is not a QuamMacro subclass or import string.
    """
    if isinstance(factory, type):
        if not issubclass(factory, QuamMacro):
            raise TypeError(f"Macro factory must be a QuamMacro subclass, got {factory.__name__}.")
    elif not isinstance(factory, str):
        raise TypeError(
            f"Macro factory must be a QuamMacro subclass or 'module:Class' string, "
            f"got {type(factory).__name__}."
        )
    entry: dict[str, Any] = {"factory": factory}
    if params:
        entry["params"] = params
    return entry


def disabled() -> dict[str, Any]:
    """Create a disabled override entry that removes the macro or pulse."""
    return {"enabled": False}


def pulse(pulse_type: str, **params: Any) -> dict[str, Any]:
    """Create a pulse override entry.

    Args:
        pulse_type: Pulse class name (``"GaussianPulse"``, ``"SquarePulse"``,
            ``"SquareReadoutPulse"``, ``"DragPulse"``).
        **params: Pulse constructor keyword arguments (``length``, ``amplitude``,
            ``sigma``, etc.).

    Returns:
        Override dict in the format expected by pulse wiring.
    """
    return {"type": pulse_type, **params}


@dataclass(frozen=True)
class ComponentOverrides:
    """Typed container grouping macro and pulse overrides for one component."""

    macros: dict[str, dict[str, Any]] = field(default_factory=dict)
    pulses: dict[str, dict[str, Any]] = field(default_factory=dict)

    def _to_dict(self) -> dict[str, Any]:
        """Convert to the internal dict format."""
        result: dict[str, Any] = {}
        if self.macros:
            result["macros"] = dict(self.macros)
        if self.pulses:
            result["pulses"] = dict(self.pulses)
        return result


def overrides(
    macros: dict[str, dict[str, Any]] | None = None,
    pulses: dict[str, dict[str, Any]] | None = None,
) -> ComponentOverrides:
    """Create a :class:`ComponentOverrides` for a component type or instance.

    Args:
        macros: Macro name -> override entry mapping (use :func:`macro` /
            :func:`disabled` to build entries).
        pulses: Pulse name -> override entry mapping (use :func:`pulse` /
            :func:`disabled` to build entries).
    """
    return ComponentOverrides(
        macros=macros or {},
        pulses=pulses or {},
    )


def _convert_typed_overrides(
    component_overrides: Mapping[type | str, ComponentOverrides | Mapping] | None,
    instance_overrides: Mapping[str, ComponentOverrides | Mapping] | None,
) -> dict[str, Any]:
    """Convert typed override kwargs to the internal dict format.

    Accepts class objects or strings as component type keys, and
    ``ComponentOverrides`` or raw dicts as values.
    """
    result: dict[str, Any] = {}

    if component_overrides:
        types_dict: dict[str, Any] = {}
        for key, value in component_overrides.items():
            type_name = key.__name__ if isinstance(key, type) else str(key)
            if isinstance(value, ComponentOverrides):
                types_dict[type_name] = value._to_dict()
            elif isinstance(value, Mapping):
                types_dict[type_name] = dict(value)
            else:
                raise TypeError(
                    f"component_overrides[{type_name}] must be a ComponentOverrides "
                    f"or mapping, got {type(value).__name__}."
                )
        result["component_types"] = types_dict

    if instance_overrides:
        instances_dict: dict[str, Any] = {}
        for path, value in instance_overrides.items():
            if not isinstance(path, str):
                raise TypeError(
                    f"Instance override keys must be strings, got {type(path).__name__}."
                )
            if isinstance(value, ComponentOverrides):
                instances_dict[path] = value._to_dict()
            elif isinstance(value, Mapping):
                instances_dict[path] = dict(value)
            else:
                raise TypeError(
                    f"instance_overrides[{path!r}] must be a ComponentOverrides "
                    f"or mapping, got {type(value).__name__}."
                )
        result["instances"] = instances_dict

    return result
