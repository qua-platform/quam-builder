"""Gate-level operations for quantum-dot components using QuAM OperationsRegistry.

OperationsRegistry is a typed facade that provides operation names (e.g. `x180`,
`measure`) as callables; each call dispatches to the component's macro at runtime.
Use `operations_registry.x180(q)` when writing generic algorithms that work across
component types; use `q.x180()` for component-specific code where the component
type is known. OperationsRegistry is not required for most users — `q.x180()` is
the natural direct call; the registry is a convenience for protocol-style code.
Each registered function here is intentionally empty because the registry uses
the function signature and name as operation metadata and dispatches to
`component.macros[operation_name]` at runtime.
"""

from quam.core import OperationsRegistry
from quam.components.quantum_components import Qubit, QubitPair, QuantumComponent

__all__ = [
    "operations_registry",
    "initialize",
    "measure",
    "empty",
    "xy_drive",
    "x",
    "y",
    "z",
    "x180",
    "x90",
    "x_neg90",
    "y180",
    "y90",
    "y_neg90",
    "z180",
    "z90",
    "z_neg90",
    "I",
    "cnot",
    "cz",
    "swap",
    "iswap",
]


operations_registry = OperationsRegistry()


@operations_registry.register_operation
def initialize(component: QuantumComponent, **kwargs):
    """Dispatch to component.macros['initialize']."""


@operations_registry.register_operation
def measure(component: QuantumComponent, **kwargs):
    """Dispatch to component.macros['measure']."""


@operations_registry.register_operation
def empty(component: QuantumComponent, **kwargs):
    """Dispatch to component.macros['empty']."""


@operations_registry.register_operation
def xy_drive(component: Qubit, **kwargs):
    """Dispatch to component.macros['xy_drive']."""


@operations_registry.register_operation
def x(component: Qubit, **kwargs):
    """Dispatch to component.macros['x']."""


@operations_registry.register_operation
def y(component: Qubit, **kwargs):
    """Dispatch to component.macros['y']."""


@operations_registry.register_operation
def z(component: Qubit, **kwargs):
    """Dispatch to component.macros['z']."""


@operations_registry.register_operation
def x180(component: Qubit, **kwargs):
    """Dispatch to component.macros['x180']."""


@operations_registry.register_operation
def x90(component: Qubit, **kwargs):
    """Dispatch to component.macros['x90']."""


@operations_registry.register_operation
def x_neg90(component: Qubit, **kwargs):
    """Dispatch to component.macros['x_neg90']."""


@operations_registry.register_operation
def y180(component: Qubit, **kwargs):
    """Dispatch to component.macros['y180']."""


@operations_registry.register_operation
def y90(component: Qubit, **kwargs):
    """Dispatch to component.macros['y90']."""


@operations_registry.register_operation
def y_neg90(component: Qubit, **kwargs):
    """Dispatch to component.macros['y_neg90']."""


@operations_registry.register_operation
def z180(component: Qubit, **kwargs):
    """Dispatch to component.macros['z180']."""


@operations_registry.register_operation
def z90(component: Qubit, **kwargs):
    """Dispatch to component.macros['z90']."""


@operations_registry.register_operation
def z_neg90(component: Qubit, **kwargs):
    """Dispatch to component.macros['z_neg90']."""


@operations_registry.register_operation
def I(component: Qubit, **kwargs):
    """Dispatch to component.macros['I']."""


@operations_registry.register_operation
def cnot(component: QubitPair, **kwargs):
    """Dispatch to component.macros['cnot']."""


@operations_registry.register_operation
def cz(component: QubitPair, **kwargs):
    """Dispatch to component.macros['cz']."""


@operations_registry.register_operation
def swap(component: QubitPair, **kwargs):
    """Dispatch to component.macros['swap']."""


@operations_registry.register_operation
def iswap(component: QubitPair, **kwargs):
    """Dispatch to component.macros['iswap']."""
