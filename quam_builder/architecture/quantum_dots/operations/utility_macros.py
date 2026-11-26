"""Default utility macros for quantum-dot macro dispatch.

This module was previously located under ``quam_builder.tools.macros``. It lives
under the quantum-dots architecture because it is part of the macro registry
used by :class:`~quam_builder.architecture.quantum_dots.operations.macro_catalog.UtilityMacroCatalog`.
"""

from __future__ import annotations

from typing import Any, List, Optional

from qm import qua
from qm.qua._expressions import QuaVariable, Scalar
from quam.core import quam_dataclass
from quam.core.macro.quam_macro import QuamMacro

__all__ = [
    "AlignMacro",
    "WaitMacro",
    "UTILITY_MACRO_FACTORIES",
]


@quam_dataclass()
class AlignMacro(QuamMacro):
    """Macro for synchronizing multiple quantum elements.

    Aligns timing across elements to ensure synchronized operations.
    """

    def apply(self, *elements, **kwargs) -> Any:
        """Execute alignment.

        Args:
            *elements: Optional elements to align (if none, aligns all)
            **kwargs: Additional keyword arguments
        """
        qua.align(*elements)

    @property
    def inferred_duration(self) -> Optional[float]:
        """Duration is zero (synchronization point)."""
        return 0.0


@quam_dataclass()
class WaitMacro(QuamMacro):
    """Macro for inserting wait/delay periods.

    Attributes:
        duration: Wait duration in clock cycles (default: 4, which is 16 ns).
            ``qua.wait`` takes this unit directly.
        elements: Optional list of elements to wait on
    """

    duration: Scalar[int] = 4
    elements: Optional[List[QuaVariable]] = None

    def apply(self, duration: Optional[int] = None, **kwargs) -> Any:
        """Execute wait operation.

        Args:
            duration: Optional override for the wait, in clock cycles.
            **kwargs: Additional keyword arguments
        """
        t = duration if duration is not None else self.duration
        qua.wait(t)

    @property
    def inferred_duration(self) -> Optional[float]:
        """Wait duration in seconds."""
        return self.duration * 4e-9


UTILITY_MACRO_FACTORIES = {
    "align": AlignMacro,
    "wait": WaitMacro,
}

