"""Macro runtime entry points for quantum-dot components.

Exports:
    load_macro_profile: Read TOML macro profile data.
    wire_machine_macros: Materialize defaults and apply user overrides.
"""

from .wiring import load_macro_profile, wire_machine_macros

__all__ = [
    "load_macro_profile",
    "wire_machine_macros",
]
