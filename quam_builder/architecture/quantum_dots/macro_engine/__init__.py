"""Macro runtime entry points for quantum-dot components.

Exports:
    wire_machine_macros: Wire macros and pulses onto a machine (main entry point).
    MacroWirer: Materializes macros from a MacroRegistry.
    PulseWirer: Materializes default pulses onto channels.
    DISABLED: Sentinel to remove a macro in override dicts.

For the catalog protocol and registry classes, import from
:mod:`quam_builder.architecture.quantum_dots.operations.macro_catalog`.
"""

from .wiring import MacroWirer, PulseWirer, wire_machine_macros

from quam_builder.architecture.quantum_dots.operations.macro_catalog import DISABLED

__all__ = [
    "wire_machine_macros",
    "MacroWirer",
    "PulseWirer",
    "DISABLED",
]
