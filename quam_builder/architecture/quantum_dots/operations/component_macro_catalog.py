"""Default component->macro catalog registration for quantum-dot architecture."""

from __future__ import annotations

from quam_builder.architecture.quantum_dots.operations.default_macros import (
    QPU_STATE_MACROS,
    SINGLE_QUBIT_MACROS,
    STATE_POINT_MACROS,
    TWO_QUBIT_MACROS,
)
from quam_builder.architecture.quantum_dots.operations.macro_registry import (
    register_component_macro_factories,
)

_REGISTERED = False

__all__ = [
    "register_default_component_macro_factories",
]


def register_default_component_macro_factories() -> None:
    """Register built-in macro factories for core quantum-dot component types.

    Registration is idempotent and intentionally centralized to keep default
    behavior decoupled from component class definitions.
    """
    global _REGISTERED
    if _REGISTERED:
        return

    # Import lazily to avoid import-cycle side effects during module initialization.
    from quam_builder.architecture.quantum_dots.components import QPU
    from quam_builder.architecture.quantum_dots.qubit import LDQubit
    from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair

    register_component_macro_factories(QPU, QPU_STATE_MACROS)
    register_component_macro_factories(LDQubit, SINGLE_QUBIT_MACROS)
    register_component_macro_factories(LDQubitPair, TWO_QUBIT_MACROS)

    # Phase 1 additions: QuantumDot voltage-only components
    from quam_builder.architecture.quantum_dots.components.quantum_dot import (
        QuantumDot,
    )
    from quam_builder.architecture.quantum_dots.components.quantum_dot_pair import (
        QuantumDotPair,
    )
    from quam_builder.architecture.quantum_dots.components.sensor_dot import (
        SensorDot,
    )
    from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
        ExchangeStateMacro,
        MeasurePSBPairMacro,
        SensorDotMeasureMacro,
    )
    from quam_builder.architecture.quantum_dots.operations.names import (
        VoltagePointName,
    )

    register_component_macro_factories(QuantumDot, STATE_POINT_MACROS)
    qdpair_macros = {
        **STATE_POINT_MACROS,
        VoltagePointName.MEASURE.value: MeasurePSBPairMacro,
        VoltagePointName.EXCHANGE.value: ExchangeStateMacro,
    }
    register_component_macro_factories(QuantumDotPair, qdpair_macros)
    # SensorDot inherits from QuantumDot — replace=True prevents initialize/empty
    # from flowing down via MRO resolution. CAT-03: measure only.
    register_component_macro_factories(
        SensorDot,
        {VoltagePointName.MEASURE.value: SensorDotMeasureMacro},
        replace=True,
    )

    _REGISTERED = True


def _reset_registration() -> None:
    """Reset global registration state. FOR TESTING ONLY.

    Called by the reset_catalog pytest fixture to ensure each test that
    explicitly verifies registration behavior starts from a clean slate.
    """
    global _REGISTERED
    _REGISTERED = False
