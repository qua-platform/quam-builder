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
from quam.core import OperationsRegistry
from quam.components.quantum_components import Qubit, QubitPair, QuantumComponent

__all__ = [
    "operations_registry",
    # State operations
    "initialize",
    "measure",
    "operate",
    "idle",
    # Single-qubit rotations (X)
    "x180",
    "x90",
    "x_neg90",
    # Single-qubit rotations (Y)
    "y180",
    "y90",
    "y_neg90",
    # Single-qubit rotations (Z)
    "z180",
    "z90",
    "z_neg90",
    # Identity
    "I",
    # Two-qubit gates
    "cnot",
    "cz",
    "swap",
    "iswap",
]


# ============================================================================
# Operations Registry
# ============================================================================

# Main registry for all quantum dot operations
operations_registry = OperationsRegistry()

# ============================================================================
# State Preparation and Measurement Operations
# ============================================================================

@operations_registry.register_operation
def initialize(component: QuantumComponent, **kwargs):
    """
    Initialize component to its ground state.

    This will trigger component.macros["initialize"].apply(**kwargs)

    Args:
        component: QuantumDot, SensorDot, LDQubit, or any VoltagePointMacroMixin component
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def measure(component: QuantumComponent, **kwargs):
    """
    Perform measurement on component.

    This will trigger component.macros["measure"].apply(**kwargs)

    Args:
        component: QuantumDot, SensorDot, LDQubit, or any VoltagePointMacroMixin component
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def operate(component: QuantumComponent, **kwargs):
    """
    Move component to operation voltage point.

    This will trigger component.macros["operate"].apply(**kwargs)

    Args:
        component: QuantumDot, SensorDot, LDQubit, or any VoltagePointMacroMixin component
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def idle(component: QuantumComponent, **kwargs):
    """
    Move component to idle voltage point.

    This will trigger component.macros["idle"].apply(**kwargs)

    Args:
        component: QuantumDot, SensorDot, LDQubit, or any VoltagePointMacroMixin component
        **kwargs: Optional parameter overrides (e.g., hold_duration=200)
    """
    pass


# ============================================================================
# Single-Qubit X Rotations
# ============================================================================

@operations_registry.register_operation
def x180(component: Qubit, **kwargs):
    """
    Apply 180-degree rotation around X axis (π pulse).

    This will trigger component.macros["x180"].apply(**kwargs)

    Args:
        component: LDQubit or any component with x180 pulse operation
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def x90(component: Qubit, **kwargs):
    """
    Apply 90-degree rotation around X axis (π/2 pulse).

    This will trigger component.macros["x90"].apply(**kwargs)

    Args:
        component: LDQubit or any component with x90 pulse operation
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def x_neg90(component: Qubit, **kwargs):
    """
    Apply -90-degree rotation around X axis (-π/2 pulse).

    This will trigger component.macros["x_neg90"].apply(**kwargs)

    Args:
        component: LDQubit or any component with x_neg90 pulse operation
        **kwargs: Optional parameter overrides
    """
    pass


# ============================================================================
# Single-Qubit Y Rotations
# ============================================================================

@operations_registry.register_operation
def y180(component: Qubit, **kwargs):
    """
    Apply 180-degree rotation around Y axis (π pulse).

    This will trigger component.macros["y180"].apply(**kwargs)

    Args:
        component: LDQubit or any component with y180 pulse operation
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def y90(component: Qubit, **kwargs):
    """
    Apply 90-degree rotation around Y axis (π/2 pulse).

    This will trigger component.macros["y90"].apply(**kwargs)

    Args:
        component: LDQubit or any component with y90 pulse operation
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def y_neg90(component: Qubit, **kwargs):
    """
    Apply -90-degree rotation around Y axis (-π/2 pulse).

    This will trigger component.macros["y_neg90"].apply(**kwargs)

    Args:
        component: LDQubit or any component with y_neg90 pulse operation
        **kwargs: Optional parameter overrides
    """
    pass


# ============================================================================
# Single-Qubit Z Rotations
# ============================================================================

@operations_registry.register_operation
def z180(component: Qubit, **kwargs):
    """
    Apply 180-degree rotation around Z axis (π pulse).

    This will trigger component.macros["z180"].apply(**kwargs)

    Args:
        component: LDQubit or any component with z180 pulse operation
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def z90(component: Qubit, **kwargs):
    """
    Apply 90-degree rotation around Z axis (π/2 pulse).

    This will trigger component.macros["z90"].apply(**kwargs)

    Args:
        component: LDQubit or any component with z90 pulse operation
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def z_neg90(component: Qubit, **kwargs):
    """
    Apply -90-degree rotation around Z axis (-π/2 pulse).

    This will trigger component.macros["z_neg90"].apply(**kwargs)

    Args:
        component: LDQubit or any component with z_neg90 pulse operation
        **kwargs: Optional parameter overrides
    """
    pass


# ============================================================================
# Identity Operation
# ============================================================================

@operations_registry.register_operation
def I(component: Qubit, **kwargs):
    """
    Apply identity operation (no-op or wait).

    This will trigger component.macros["I"].apply(**kwargs)

    Args:
        component: Any component with identity operation
        **kwargs: Optional parameter overrides (e.g., duration)
    """
    pass


# ============================================================================
# Two-Qubit Gates
# ============================================================================

@operations_registry.register_operation
def cnot(component: QubitPair, **kwargs):
    """
    Apply controlled-NOT gate on qubit pair.

    This will trigger component.macros["cnot"].apply(**kwargs)

    Args:
        component: LDQubitPair or any two-qubit component with cnot operation
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def cz(component: QubitPair, **kwargs):
    """
    Apply controlled-Z gate on qubit pair.

    This will trigger component.macros["cz"].apply(**kwargs)

    Args:
        component: LDQubitPair or any two-qubit component with cz operation
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def swap(component: QubitPair, **kwargs):
    """
    Apply SWAP gate on qubit pair.

    This will trigger component.macros["swap"].apply(**kwargs)

    Args:
        component: LDQubitPair or any two-qubit component with swap operation
        **kwargs: Optional parameter overrides
    """
    pass


@operations_registry.register_operation
def iswap(component: QubitPair, **kwargs):
    """
    Apply iSWAP gate on qubit pair.

    This will trigger component.macros["iswap"].apply(**kwargs)

    Args:
        component: LDQubitPair or any two-qubit component with iswap operation
        **kwargs: Optional parameter overrides
    """
    pass