"""Two-qubit default macros for quantum-dot qubit pairs."""

# Framework macro base classes introduce deep inheritance chains by design.
# pylint: disable=too-many-ancestors

from quam.components.macro import QubitPairMacro

from quam_builder.architecture.quantum_dots.operations.names import (
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    EmptyStateMacro,
    ExchangeStateMacro,
    InitializeStateMacro,
    _owner_component,
)

__all__ = [
    "TWO_QUBIT_MACROS",
    "Initialize2QMacro",
    "Measure2QMacro",
    "Empty2QMacro",
    "Exchange2QMacro",
    "CNOTMacro",
    "CZMacro",
    "SwapMacro",
    "ISwapMacro",
]


class Initialize2QMacro(InitializeStateMacro, QubitPairMacro):
    """Initialize qubit pair by ramping to the `initialize` voltage point."""

    point: str = VoltagePointName.INITIALIZE.value


class Measure2QMacro(QubitPairMacro):
    """PSB measure macro for LDQubitPair.

    Delegates to the underlying QuantumDotPair's measure macro,
    which performs the full PSB readout chain (voltage step -> sensor
    dot readout -> threshold -> QUA boolean).
    """

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        """Delegate measurement to the underlying quantum_dot_pair."""
        owner = _owner_component(self)
        qd_pair = getattr(owner, "quantum_dot_pair", None)
        if qd_pair is None:
            raise ValueError(f"LDQubitPair '{owner.id}' has no quantum_dot_pair for readout.")
        return qd_pair.macros[TwoQubitMacroName.MEASURE].apply(**kwargs)


class Empty2QMacro(EmptyStateMacro, QubitPairMacro):
    """Move qubit pair to the `empty` voltage point."""

    point: str = VoltagePointName.EMPTY.value


class Exchange2QMacro(ExchangeStateMacro, QubitPairMacro):
    """Exchange macro for LDQubitPair — ramp to exchange, wait, ramp back."""

    point: str = VoltagePointName.EXCHANGE.value


class _Unsupported2QGateMacro(QubitPairMacro):
    """Default placeholder for two-qubit gates requiring calibration-specific logic."""

    gate_name: str

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        """Raise explicit guidance to register a calibration-specific override."""
        raise NotImplementedError(
            f"Default macro for '{self.gate_name}' is not yet implemented for "
            f"component '{self.qubit_pair.id}'. Register a calibrated macro override."
        )


class CNOTMacro(_Unsupported2QGateMacro):
    """Default placeholder for CNOT (override required)."""

    gate_name: str = TwoQubitMacroName.CNOT.value


class CZMacro(_Unsupported2QGateMacro):
    """Default placeholder for CZ (override required)."""

    gate_name: str = TwoQubitMacroName.CZ.value


class SwapMacro(_Unsupported2QGateMacro):
    """Default placeholder for SWAP (override required)."""

    gate_name: str = TwoQubitMacroName.SWAP.value


class ISwapMacro(_Unsupported2QGateMacro):
    """Default placeholder for iSWAP (override required)."""

    gate_name: str = TwoQubitMacroName.ISWAP.value


TWO_QUBIT_MACROS = {
    VoltagePointName.INITIALIZE.value: Initialize2QMacro,
    VoltagePointName.MEASURE.value: Measure2QMacro,
    VoltagePointName.EMPTY.value: Empty2QMacro,
    TwoQubitMacroName.CNOT.value: CNOTMacro,
    TwoQubitMacroName.CZ.value: CZMacro,
    TwoQubitMacroName.SWAP.value: SwapMacro,
    TwoQubitMacroName.ISWAP.value: ISwapMacro,
    TwoQubitMacroName.EXCHANGE.value: Exchange2QMacro,
}
# Default two-qubit macro factories for ``LDQubitPair`` components.
