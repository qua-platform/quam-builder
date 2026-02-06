"""
Operations and macros for quantum dot calibration.

This module provides:
- Default operations registry with gate-level operations
- Default macros for state preparation, single-qubit gates, and two-qubit gates
"""

# Operations registry and operations
from .default_macros import *
from .default_operations import *

__all__ = [
    *default_macros.__all__,
    *default_operations.__all__,
]