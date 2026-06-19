"""Voltage-balanced single-qubit macros for LD qubits.

In the balanced catalog the idle state is 0 V on every channel, so the
XY drive does not need to hold the voltage gates or update the sticky
voltage-sequence bookkeeping during the microwave pulse. The macro
plays the XY pulse at its native length with angle-to-amplitude and
phase rescaling identical to :class:`XYDriveMacro`.
"""

# pylint: disable=too-many-ancestors
from __future__ import annotations
from typing import Any

import math

from qm import qua
from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    XYDriveMacro,
    _compose_amplitude_scale,
    _quantize_ns,
    _resolve_qubit_pair,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    _owner_component,
)
from quam_builder.architecture.quantum_dots.operations.voltage_balanced_macros.state_macros import (
    BalancedInitializeMacro, _point_voltages,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.tools.qua_tools import CLOCK_CYCLE_NS, is_qua_type
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from qualang_tools.units import unit

@quam_dataclass
class BalancedXYDriveMacro(XYDriveMacro):
    pass
