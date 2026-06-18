"""
Operations and macros for quantum dot calibration.

This module provides:
- Default operations registry with gate-level operations
- Default macros for state preparation, single-qubit gates, and two-qubit gates
- Canonical name constants for voltage points and supported macros
- A catalog-based macro registry for decoupled macro-default wiring
- Channel-aware builders for the default pulse materialization pass
"""

from .macro_catalog import *
from .pulse_catalog import *
from .names import *
from .default_macros import *
from .default_operations import *

__all__ = [
    *macro_catalog.__all__,
    *pulse_catalog.__all__,
    *names.__all__,
    *default_macros.__all__,
    *default_operations.__all__,
]
