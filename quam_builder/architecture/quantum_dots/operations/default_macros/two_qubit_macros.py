"""
Two-qubit gate macros for quantum dot qubit pairs.

These macros implement two-qubit gates like CNOT, CZ, SWAP, and iSWAP.
"""
from quam.components.macro import QubitPairMacro


__all__ = [
    "TWO_QUBIT_MACROS",
    "Initialize2QMacro",
    "Measure2QMacro",
    "Operate2QMacro",
    "Idle2QMacro",
    "CNOTMacro",
    "CZMacro",
    "SwapMacro",
    "ISwapMacro",
]


# ============================================================================
# State Macros
# ============================================================================

class Initialize2QMacro(QubitPairMacro):
    """Initialize component to its ground state."""
    ramp_duration: float = 1.0
    hold_duration: float = 1.0
    def apply(self, ramp_duration=None, hold_duration=None, **kwargs):
        """
        Apply initialization sequence.

        Args:
            **kwargs: Optional parameter overrides
        """
        ramp_duration = self.ramp_duration if ramp_duration is None else ramp_duration
        hold_duration = self.hold_duration if hold_duration is None else hold_duration

        self.qubit.ramp_to_point('initialize', ramp_duration, hold_duration)

class Measure2QMacro(QubitPairMacro):
    """Perform measurement on component."""

    def apply(self, **kwargs):
        """
        Apply measurement sequence.

        Args:
            **kwargs: Optional parameter overrides
        """
        pass


class Operate2QMacro(QubitPairMacro):
    """Move component to operation voltage point."""

    def apply(self, **kwargs):
        """
        Apply operation point transition.

        Args:
            **kwargs: Optional parameter overrides
        """
        pass


class Idle2QMacro(QubitPairMacro):
    """Move component to idle voltage point."""

    def apply(self, **kwargs):
        """
        Apply idle point transition.

        Args:
            **kwargs: Optional parameter overrides (e.g., hold_duration)
        """
        pass


# ============================================================================
# Two-Qubit Gate Macros
# ============================================================================

class CNOTMacro(QubitPairMacro):
    """Apply controlled-NOT gate on qubit pair."""

    def apply(self, **kwargs):
        """
        Apply CNOT gate.

        Args:
            **kwargs: Optional parameter overrides
        """
        pass


class CZMacro(QubitPairMacro):
    """Apply controlled-Z gate on qubit pair."""

    def apply(self, **kwargs):
        """
        Apply CZ gate.

        Args:
            **kwargs: Optional parameter overrides
        """
        pass


class SwapMacro(QubitPairMacro):
    """Apply SWAP gate on qubit pair."""

    def apply(self, **kwargs):
        """
        Apply SWAP gate.

        Args:
            **kwargs: Optional parameter overrides
        """
        pass


class ISwapMacro(QubitPairMacro):
    """Apply iSWAP gate on qubit pair."""

    def apply(self, **kwargs):
        """
        Apply iSWAP gate.

        Args:
            **kwargs: Optional parameter overrides
        """
        pass


# ============================================================================
# Two Qubit Macros Dictionary
# ============================================================================

TWO_QUBIT_MACROS = {
    # State macros
    "initialize": Initialize2QMacro,
    "measure": Measure2QMacro,
    "operate": Operate2QMacro,
    "idle": Idle2QMacro,
    # Two qubit macros
    "cnot": CNOTMacro,
    "cz": CZMacro,
    "swap": SwapMacro,
    "iswap": ISwapMacro,
}