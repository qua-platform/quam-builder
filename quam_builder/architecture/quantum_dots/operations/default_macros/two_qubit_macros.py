"""Two-qubit default macros for quantum-dot qubit pairs."""

# Framework macro base classes introduce deep inheritance chains by design.
# pylint: disable=too-many-ancestors

from quam.components.macro import QubitPairMacro

from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    EmptyStateMacro,
    InitializeStateMacro,
    MeasureStateMacro,
)

__all__ = [
    "TWO_QUBIT_MACROS",
    "Initialize2QMacro",
    "Measure2QMacro",
    "Empty2QMacro",
    "CNOTMacro",
    "CZMacro",
    "SwapMacro",
    "ISwapMacro",
]


class Initialize2QMacro(InitializeStateMacro, QubitPairMacro):
    """Initialize qubit pair by ramping to the `initialize` voltage point."""


class Measure2QMacro(MeasureStateMacro, QubitPairMacro):
    """Move qubit pair to the `measure` voltage point."""


class Empty2QMacro(EmptyStateMacro, QubitPairMacro):
    """Move qubit pair to the `empty` voltage point."""


class _Unsupported2QGateMacro(QubitPairMacro):
    """Default placeholder for two-qubit gates requiring calibration-specific logic."""

    gate_name: str

    def apply(self, **kwargs):
        """Raise explicit guidance to register a calibration-specific override."""
        raise NotImplementedError(
            f"Default macro for '{self.gate_name}' is intentionally not implemented for "
            f"component '{self.qubit_pair.id}'. Register a calibrated macro override."
        )


class CNOTMacro(_Unsupported2QGateMacro):
    """Default placeholder for CNOT (override required)."""

    gate_name: str = "cnot"


class CZMacro(_Unsupported2QGateMacro):
    """Default placeholder for CZ (override required)."""

    gate_name: str = "cz"


class SwapMacro(_Unsupported2QGateMacro):
    """Default placeholder for SWAP (override required)."""

    gate_name: str = "swap"


class ISwapMacro(_Unsupported2QGateMacro):
    """Default placeholder for iSWAP (override required)."""

    gate_name: str = "iswap"


TWO_QUBIT_MACROS = {
    "initialize": Initialize2QMacro,
    "measure": Measure2QMacro,
    "empty": Empty2QMacro,
    "cnot": CNOTMacro,
    "cz": CZMacro,
    "swap": SwapMacro,
    "iswap": ISwapMacro,
}
# Default two-qubit macro factories for ``LDQubitPair`` components.
