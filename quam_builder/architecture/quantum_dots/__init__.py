"""
Quantum Dot Architecture for QuAM.

This module provides components and tools for building quantum dot-based quantum processors.
"""

# Components
from quam_builder.architecture.quantum_dots.components import *

# Operations (gate-level operations registry)
from quam_builder.architecture.quantum_dots.examples.operations import operations_registry

# QPU
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

# Qubits
from quam_builder.architecture.quantum_dots.qubit import LDQubit

from . import macros
from .macros import *

__all__ = [
    "BaseQuamQD",
    "LDQubit",
    "operations_registry",
    *macros.__all__,
]
