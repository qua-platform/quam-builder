"""Compatibility shims for voltage sequence modules.

This package re-exports voltage sequence tools under the
`quam_builder.architecture.quantum_dots.voltage_sequence` namespace to
preserve legacy import paths used by the tests.
"""

from . import gate_set, voltage_sequence, constants
from .gate_set import *  # noqa: F401,F403
from .voltage_sequence import *  # noqa: F401,F403
from .constants import *  # noqa: F401,F403

__all__ = [
    *gate_set.__all__,
    *voltage_sequence.__all__,
    *constants.__all__,
]
