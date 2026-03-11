"""
Operations and macros for quantum dot calibration.

This module provides:
- Default operations registry with gate-level operations
- Default macros for state preparation, single-qubit gates, and two-qubit gates
- Canonical name constants for voltage points and supported macros
- A component-type macro registry for decoupled macro-default wiring
"""

# Operations registry and operations
from .component_macro_catalog import *
from .macro_registry import *
from .names import *
from .default_macros import *
from .default_operations import *

__all__ = [
    *component_macro_catalog.__all__,
    *macro_registry.__all__,
    *names.__all__,
    *default_macros.__all__,
    *default_operations.__all__,
]
