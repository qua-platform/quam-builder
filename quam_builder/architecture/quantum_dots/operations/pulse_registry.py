"""Registry for attaching default pulse factories to component types.

Mirrors the macro registry pattern
(:mod:`~quam_builder.architecture.quantum_dots.operations.macro_registry`):
pulse-default wiring is decoupled from component/base classes while keeping
registration explicit and local to the architecture package.

How it works
------------
1. At import time, :func:`register_component_pulse_factories` is called for
   each component type that should carry default pulses (e.g. ``LDQubit``,
   ``SensorDot``).  The registry stores a mapping of
   ``pulse_name -> factory_callable`` keyed by fully-qualified class name.

2. At wiring time, :func:`get_default_pulse_factories` walks the component's
   MRO and merges registered factories (base -> derived, later wins).

3. The wiring layer (:func:`~quam_builder.architecture.quantum_dots.macro_engine.wiring._ensure_default_pulses`)
   calls the factories and writes the resulting ``Pulse`` instances into the
   component's ``operations`` dict — but only for pulse names that are not
   already present (user-supplied pulses always take precedence).

Example::

    from quam_builder.architecture.quantum_dots.operations.pulse_registry import (
        register_component_pulse_factories,
        get_default_pulse_factories,
    )
    from quam.components.pulses import SquarePulse

    register_component_pulse_factories(
        MyCustomQubit,
        {"pi": lambda: SquarePulse(length=100, amplitude=0.3)},
    )

    # Later, at wiring time:
    factories = get_default_pulse_factories(my_qubit_instance)
    # factories == {"pi": <lambda>}
"""

from __future__ import annotations

from typing import Callable, Dict, Mapping

from quam.components.pulses import Pulse

__all__ = [
    "PulseFactoryMap",
    "register_component_pulse_factories",
    "get_default_pulse_factories",
]

PulseFactoryMap = Dict[str, Callable[[], Pulse]]
"""Type alias: maps pulse names to no-arg factory callables returning Pulse."""

_COMPONENT_PULSE_FACTORIES: Dict[str, PulseFactoryMap] = {}
# Internal registry keyed by fully-qualified component class name.


def _component_key(component_type: type) -> str:
    """Create a stable key for component-type registrations.

    Uses the fully-qualified module + qualname so that two classes with the
    same short name in different modules never collide.
    """
    return f"{component_type.__module__}.{component_type.__qualname__}"


def register_component_pulse_factories(
    component_type: type,
    pulse_factories: Mapping[str, Callable[[], Pulse]],
) -> None:
    """Register pulse factories for a component type.

    If the component type is already registered, new entries are merged
    on top (new keys win, existing keys are preserved).

    Args:
        component_type: Target component class (e.g. ``LDQubit``).
        pulse_factories: Mapping of pulse name to factory callable.
            Each factory should be a no-arg callable returning a
            :class:`~quam.components.pulses.Pulse` instance.

    Example::

        register_component_pulse_factories(
            LDQubit,
            {"x180": lambda: GaussianPulse(length=1000, amplitude=0.2, sigma=167)},
        )
    """
    key = _component_key(component_type)
    if key not in _COMPONENT_PULSE_FACTORIES:
        _COMPONENT_PULSE_FACTORIES[key] = dict(pulse_factories)
        return

    merged = dict(_COMPONENT_PULSE_FACTORIES[key])
    merged.update(pulse_factories)
    _COMPONENT_PULSE_FACTORIES[key] = merged


def get_default_pulse_factories(component: object) -> PulseFactoryMap:
    """Resolve default pulse factories for a component instance.

    Resolution follows the MRO (base -> derived); later entries win.
    This means a derived class can override individual pulse names
    registered on a base class.

    Args:
        component: Component instance for which to resolve defaults.

    Returns:
        Merged ``PulseFactoryMap`` with the effective pulse defaults.
    """
    resolved: PulseFactoryMap = {}

    for component_type in reversed(type(component).mro()):
        key = _component_key(component_type)
        if key in _COMPONENT_PULSE_FACTORIES:
            resolved.update(_COMPONENT_PULSE_FACTORIES[key])

    return resolved


def _reset_registry() -> None:
    """Clear all registered pulse factories. **FOR TESTING ONLY.**"""
    _COMPONENT_PULSE_FACTORIES.clear()
