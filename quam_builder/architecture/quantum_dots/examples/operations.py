"""
Gate-level operations for quantum dot components using QuAM's OperationsRegistry.

This module demonstrates how to register voltage point operations and pulse operations
as gate-level operations that can be called directly in QUA code.

The OperationsRegistry allows you to:
1. Define operations at a high level with type hints
2. Automatically dispatch to the correct macro implementation
3. Get type checking and IDE autocomplete support
4. Write cleaner QUA code
"""
from quam import QuamComponent
from typing import TYPE_CHECKING

from quam.core import OperationsRegistry

from quam_builder.architecture.quantum_dots.components import QuantumDot, SensorDot
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair
from quam_builder.architecture.quantum_dots.components import VoltagePointMacroMixin

__all__ = [
    "operations_registry",
    "voltage_operations_registry",
    # Voltage operations
    "idle",
    "load",
    "readout",
    # Pulse operations
    "x180",
    "y180",
    "x90",
    "y90",
    # Mixed sequences
    "rabi",
]


# ============================================================================
# Operations Registry
# ============================================================================

# Main registry for all quantum dot operations (voltage + pulse)
operations_registry = OperationsRegistry()

# Optional: Separate registry for voltage-only operations
voltage_operations_registry = OperationsRegistry()


# ============================================================================
# Generic Voltage Point Operations
# ============================================================================
# These work with any component that has VoltagePointMacroMixin

@operations_registry.register_operation
def idle(component: VoltagePointMacroMixin, **kwargs):
    """
    Move component to idle voltage point.

    This will trigger component.macros["idle"].apply(**kwargs)

    Args:
        component: QuantumDot, SensorDot, LDQubit, or any VoltagePointMacroMixin component
        **kwargs: Optional parameter overrides (e.g., hold_duration=200)
    """
    pass


@operations_registry.register_operation
def load(component: VoltagePointMacroMixin, **kwargs):
    """
    Move component to load voltage point.

    Args:
        component: Any component with voltage_sequence capability
        **kwargs: Optional parameter overrides
    """
    pass

@operations_registry.register_operation
def init(component: VoltagePointMacroMixin, **kwargs):
    """
    Move component to init voltage point.
    :param component:
    :param kwargs:
    :return:
    """
    pass

@operations_registry.register_operation
def readout(component: VoltagePointMacroMixin, **kwargs):
    """
    Move component to readout voltage point.

    Args:
        component: Any component with voltage_sequence capability
        **kwargs: Optional parameter overrides
    """
    pass


# ============================================================================
# Pulse Operations
# ============================================================================

@operations_registry.register_operation
def x180(qubit: LDQubit, **kwargs):
    """
    Apply X180 pulse (π rotation around X axis).

    This will trigger qubit.macros["x180"].apply(**kwargs)

    Args:
        qubit: LDQubit with xy_channel
        **kwargs: Optional pulse parameters (amplitude_scale, duration, etc.)
    """
    pass


@operations_registry.register_operation
def y180(qubit: LDQubit, **kwargs):
    """
    Apply Y180 pulse (π rotation around Y axis).

    Args:
        qubit: LDQubit with xy_channel
        **kwargs: Optional pulse parameters
    """
    pass


@operations_registry.register_operation
def x90(qubit: LDQubit, **kwargs):
    """
    Apply X90 pulse (π/2 rotation around X axis).

    Args:
        qubit: LDQubit with xy_channel
        **kwargs: Optional pulse parameters
    """
    pass


@operations_registry.register_operation
def y90(qubit: LDQubit, **kwargs):
    """
    Apply Y90 pulse (π/2 rotation around Y axis).

    Args:
        qubit: LDQubit with xy_channel
        **kwargs: Optional pulse parameters
    """
    pass


# ============================================================================
# Mixed Pulse + Voltage Operations
# ============================================================================

@operations_registry.register_operation
def rabi(qubit: VoltagePointMacroMixin, **kwargs):
    """
    Execute Rabi experiment sequence (voltage + pulse).

    Example macro definition:
        qubit.with_sequence("rabi", ["init", "x180", "readout"])

    Args:
        qubit: LDQubit with both voltage and pulse macros
        **kwargs: Optional parameter overrides
    """
    pass
