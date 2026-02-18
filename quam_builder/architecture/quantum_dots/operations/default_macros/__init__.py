"""
Default macros for quantum dot operations.

This module provides a collection of default macro implementations for
quantum dot components, organized by operation type:
- State macros: initialization, measurement, operation, and idle
- Single-qubit macros: rotations around X, Y, Z axes and identity
- Two-qubit macros: CNOT, CZ, SWAP, and iSWAP gates

The default_macros dictionary provides a unified collection of all
available macros for easy registration with quantum dot components.
"""
from .single_qubit_macros import *
from .two_qubit_macros import *


__all__ = [
    *single_qubit_macros.__all__,
    *two_qubit_macros.__all__,
]
