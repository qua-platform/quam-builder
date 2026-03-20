"""Macro runtime entry points for quantum-dot components.

Exports:
    load_macro_profile: Read TOML macro profile data.
    wire_machine_macros: Materialize defaults and apply user overrides.
    macro: Create a macro override entry with early validation.
    disabled: Create a disabled override entry (removes macro/pulse).
    pulse: Create a pulse override entry.
    overrides: Create a ComponentOverrides grouping macros and pulses.
    ComponentOverrides: Typed container for macro and pulse overrides.
"""

from .wiring import load_macro_profile, wire_machine_macros
from .overrides import macro, disabled, pulse, overrides, ComponentOverrides

__all__ = [
    "load_macro_profile",
    "wire_machine_macros",
    "macro",
    "disabled",
    "pulse",
    "overrides",
    "ComponentOverrides",
]
