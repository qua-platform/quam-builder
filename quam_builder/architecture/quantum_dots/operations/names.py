"""Canonical names for quantum-dot voltage points, macros, and operations.

This module centralizes string identifiers used by default macro registration
and by user-facing override configuration.
"""

from enum import StrEnum

__all__ = [
    "VoltagePointName",
    "SingleQubitMacroName",
    "TwoQubitMacroName",
    "X_NEG_90_ALIAS",
    "Y_NEG_90_ALIAS",
    "SINGLE_QUBIT_MACRO_ALIASES",
    "SINGLE_QUBIT_MACRO_ALIAS_MAP",
    "STATE_MACRO_NAMES",
    "SINGLE_QUBIT_MACRO_NAMES",
    "TWO_QUBIT_MACRO_NAMES",
]


class VoltagePointName(StrEnum):
    """Canonical voltage-point names used by default state macros."""

    INITIALIZE = "initialize"
    MEASURE = "measure"
    EMPTY = "empty"


class SingleQubitMacroName(StrEnum):
    """Canonical single-qubit macro names for built-in defaults."""

    XY_DRIVE = "xy_drive"
    X = "x"
    Y = "y"
    Z = "z"

    X_180 = "x180"
    X_90 = "x90"
    X_NEG_90 = "x_neg90"

    Y_180 = "y180"
    Y_90 = "y90"
    Y_NEG_90 = "y_neg90"

    Z_180 = "z180"
    Z_90 = "z90"

    IDENTITY = "I"


class TwoQubitMacroName(StrEnum):
    """Canonical two-qubit macro names for built-in defaults."""

    CNOT = "cnot"
    CZ = "cz"
    SWAP = "swap"
    ISWAP = "iswap"


X_NEG_90_ALIAS = "-x90"
Y_NEG_90_ALIAS = "-y90"
# Canonical supported alias spellings for fixed-angle rotations.

STATE_MACRO_NAMES = (
    VoltagePointName.INITIALIZE.value,
    VoltagePointName.MEASURE.value,
    VoltagePointName.EMPTY.value,
)
# Default state-macro names used across supported component types.

SINGLE_QUBIT_MACRO_ALIASES = (
    X_NEG_90_ALIAS,
    Y_NEG_90_ALIAS,
)
# Supported alias names that map onto canonical single-qubit defaults.

SINGLE_QUBIT_MACRO_ALIAS_MAP = {
    X_NEG_90_ALIAS: SingleQubitMacroName.X_NEG_90.value,
    Y_NEG_90_ALIAS: SingleQubitMacroName.Y_NEG_90.value,
}
# Alias -> canonical-name mapping used for default compatibility keys.

SINGLE_QUBIT_MACRO_NAMES = (
    *STATE_MACRO_NAMES,
    SingleQubitMacroName.XY_DRIVE.value,
    SingleQubitMacroName.X.value,
    SingleQubitMacroName.Y.value,
    SingleQubitMacroName.Z.value,
    SingleQubitMacroName.X_180.value,
    SingleQubitMacroName.X_90.value,
    SingleQubitMacroName.X_NEG_90.value,
    X_NEG_90_ALIAS,
    SingleQubitMacroName.Y_180.value,
    SingleQubitMacroName.Y_90.value,
    SingleQubitMacroName.Y_NEG_90.value,
    Y_NEG_90_ALIAS,
    SingleQubitMacroName.Z_180.value,
    SingleQubitMacroName.Z_90.value,
    SingleQubitMacroName.IDENTITY.value,
)
# Supported single-qubit macro names for default LD qubits.

TWO_QUBIT_MACRO_NAMES = (
    *STATE_MACRO_NAMES,
    TwoQubitMacroName.CNOT.value,
    TwoQubitMacroName.CZ.value,
    TwoQubitMacroName.SWAP.value,
    TwoQubitMacroName.ISWAP.value,
)
# Supported two-qubit macro names for default LD qubit pairs.
