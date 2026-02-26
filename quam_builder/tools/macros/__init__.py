"""Quantum dot macros for QUAM."""

from .composable_macros import *
from .measure_macros import *
from .default_macros import *

try:
    from .point_macros import *
except ImportError as _e:
    # Guard against the known circular import when voltage_sequence/components
    # pull in this package during their own initialisation. Re-raise anything
    # that is not caused by that cycle so genuine missing-dependency errors
    # are not silently swallowed.
    if "voltage_sequence" not in str(_e) and "VoltageSequence" not in str(_e):
        raise

__all__ = [
    *composable_macros.__all__,
    *measure_macros.__all__,
    *default_macros.__all__,
]
if "point_macros" in globals():
    __all__.extend(point_macros.__all__)
