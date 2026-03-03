"""Registry for attaching default macro factories to component types.

This decouples macro-default wiring from component/base classes while keeping
registration explicit and local to the architecture package.
"""

from __future__ import annotations

from typing import Dict, Mapping, Type

from quam.core.macro import QuamMacro

from quam_builder.tools.macros.default_macros import UTILITY_MACRO_FACTORIES

__all__ = [
    "MacroFactoryMap",
    "register_component_macro_factories",
    "get_default_macro_factories",
]

MacroFactoryMap = Dict[str, Type[QuamMacro]]
# Type alias for a macro-name to macro-class factory mapping.

_COMPONENT_MACRO_FACTORIES: Dict[str, MacroFactoryMap] = {}
# Internal registry keyed by fully-qualified component class name.

_REPLACE_KEYS: set = set()
# Keys registered with replace=True — do not inherit from bases.


def _component_key(component_type: type) -> str:
    """Create a stable key for component-type registrations."""
    return f"{component_type.__module__}.{component_type.__qualname__}"


def register_component_macro_factories(
    component_type: type,
    macro_factories: Mapping[str, Type[QuamMacro]],
    *,
    replace: bool = False,
) -> None:
    """Register macro factories for a component type.

    Args:
        component_type: Target component class.
        macro_factories: Macro name -> macro class mapping.
        replace: If True, replace any existing mapping for this component type.
            If False (default), merge into the existing mapping (new keys win).
    """
    key = _component_key(component_type)
    if replace:
        _REPLACE_KEYS.add(key)
        _COMPONENT_MACRO_FACTORIES[key] = dict(macro_factories)
        return
    if key not in _COMPONENT_MACRO_FACTORIES:
        _COMPONENT_MACRO_FACTORIES[key] = dict(macro_factories)
        return

    merged = dict(_COMPONENT_MACRO_FACTORIES[key])
    merged.update(macro_factories)
    _COMPONENT_MACRO_FACTORIES[key] = merged


def get_default_macro_factories(component: object) -> MacroFactoryMap:
    """Resolve default macro factories for a component instance.

    Resolution order:
    1. Utility factories (available on all macro-dispatch components)
    2. Registered factories for each type in the component MRO (base -> derived)

    Args:
        component: Component instance for which to resolve default macro classes.

    Returns:
        MacroFactoryMap with the effective defaults for this component.
    """
    resolved: MacroFactoryMap = dict(UTILITY_MACRO_FACTORIES)

    for component_type in reversed(type(component).mro()):
        key = _component_key(component_type)
        if key in _COMPONENT_MACRO_FACTORIES:
            if key in _REPLACE_KEYS:
                # Do not inherit from bases — use only this type's factories.
                resolved = dict(UTILITY_MACRO_FACTORIES)
                resolved.update(_COMPONENT_MACRO_FACTORIES[key])
            else:
                resolved.update(_COMPONENT_MACRO_FACTORIES[key])

    return resolved


def _reset_registry() -> None:
    """Clear all registered macro factories. FOR TESTING ONLY."""
    _COMPONENT_MACRO_FACTORIES.clear()
    _REPLACE_KEYS.clear()
