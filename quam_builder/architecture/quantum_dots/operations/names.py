"""Canonical names for quantum-dot voltage points, macros, and operations.

This module centralizes string identifiers used by default macro registration
and by user-facing override configuration.
"""

from enum import StrEnum

__all__ = [
    "VoltagePointName",
    "STATE_MACRO_NAMES",
    "SINGLE_QUBIT_MACRO_NAMES",
    "TWO_QUBIT_MACRO_NAMES",
]


class VoltagePointName(StrEnum):
    """Canonical voltage-point names used by default state macros."""

    INITIALIZE = "initialize"
    MEASURE = "measure"
    EMPTY = "empty"


STATE_MACRO_NAMES = (
    VoltagePointName.INITIALIZE.value,
    VoltagePointName.MEASURE.value,
    VoltagePointName.EMPTY.value,
)
# Default state-macro names used across supported component types.

SINGLE_QUBIT_MACRO_NAMES = (
    *STATE_MACRO_NAMES,
    "xy_drive",
    "x",
    "y",
    "z",
    "x180",
    "x90",
    "x_neg90",
    "-x90",
    "y180",
    "y90",
    "y_neg90",
    "-y90",
    "z180",
    "z90",
    "I",
)
# Supported single-qubit macro names for default LD qubits.

TWO_QUBIT_MACRO_NAMES = (
    *STATE_MACRO_NAMES,
    "cnot",
    "cz",
    "swap",
    "iswap",
)
# Supported two-qubit macro names for default LD qubit pairs.
