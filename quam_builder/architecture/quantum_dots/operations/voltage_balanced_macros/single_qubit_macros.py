"""Voltage-balanced single-qubit macros for LD qubits.

In the balanced catalog the idle state is 0 V on every channel, so the
XY drive does not need to hold the voltage gates or update the sticky
voltage-sequence bookkeeping during the microwave pulse. The macro
plays the XY pulse at its native length with the same angle-to-amplitude
scaling as :class:`XYDriveMacro`.
"""

# pylint: disable=too-many-ancestors
from __future__ import annotations

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    XYDriveMacro,
)

__all__ = ["BalancedXYDriveMacro"]


@quam_dataclass
class BalancedXYDriveMacro(XYDriveMacro):
    pass
