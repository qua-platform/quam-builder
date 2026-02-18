"""Mixin classes for quantum dot component functionality.

This module provides composable mixin classes for voltage control and macro
management, following the Single Responsibility Principle.

Mixin Hierarchy:
    VoltageControlMixin (base)
        - Base voltage operations (go_to_voltages, step_to_voltages, ramp_to_voltages)

    VoltagePointMixin(VoltageControlMixin)
        - Point management (add_point, step_to_point, ramp_to_point)

    MacroDispatchMixin
        - Macro infrastructure (__getattr__, __post_init__)

    VoltageMacroMixin(VoltagePointMixin, MacroDispatchMixin)
        - Full API combining all functionality
        - Fluent API methods (with_step_point, with_ramp_point, etc.)
"""

from .voltage_control import VoltageControlMixin
from .voltage_point import VoltagePointMixin
from .macro_dispatch import MacroDispatchMixin
from .voltage_macro import VoltageMacroMixin

__all__ = [
    "VoltageControlMixin",
    "VoltagePointMixin",
    "MacroDispatchMixin",
    "VoltageMacroMixin",
]
