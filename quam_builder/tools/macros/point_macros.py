"""Voltage point macros for quantum dot operations.

This module provides macros for voltage point operations following QUAM's
Pulse → Macro → Operation pattern with reference-based serialization.
"""

from dataclasses import field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from qm import qua
from qm.qua._expressions import QuaVariable, Scalar, to_scalar_pb_expression
from quam import QuamComponent
from quam.core import QuamComponent as QuamBaseComponent
from quam.core import quam_dataclass
from quam.core.macro.quam_macro import QuamMacro
from quam.core.operation.operations_registry import OperationsRegistry
from quam.utils import string_reference
from quam.utils.exceptions import InvalidReferenceError
from quam.utils.qua_types import QuaVariableBool

from quam_builder.tools.qua_tools import DurationType, VoltageLevelType

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD

from quam_builder.tools.voltage_sequence import VoltageSequence

__all__ = [
    "BasePointMacro",
    "StepPointMacro",
    "RampPointMacro",
]


@quam_dataclass
class BasePointMacro(QuamMacro):
    """Base class for voltage point macros using reference-based pattern.

    Encapsulates operations on pre-defined voltage points stored in gate_set.macros.
    Stores references to points rather than concrete instances for serialization.

    Attributes:
        point_ref: Reference string to VoltageTuningPoint (e.g., "#./voltage_sequence/gate_set/macros/dot_0_idle")
        hold_duration: Duration to hold final voltage (nanoseconds)
        macro_type: Type identifier ('step', 'ramp', etc.)
    """

    point_ref: Optional[str] = None
    hold_duration: Optional[int] = None
    macro_type: str = "base"

    @property
    def voltage_sequence(self) -> VoltageSequence:
        """Voltage sequence for this macro."""
        return self.parent.parent.voltage_sequence

    def _resolve_point(self, component: QuamComponent):
        """Resolve point reference to actual VoltageTuningPoint object.

        Args:
            component: Component from which to resolve reference

        Returns:
            Resolved voltage tuning point

        Raises:
            ValueError: If point_ref is not set
            TypeError: If reference doesn't resolve to VoltageTuningPoint
            InvalidReferenceError: If reference cannot be resolved
        """
        from quam_builder.architecture.quantum_dots.components.gate_set import (
            VoltageTuningPoint,
        )

        if self.point_ref is None:
            raise ValueError("point_ref is not set on this macro")

        try:
            point = string_reference.get_referenced_value(
                component,
                self.point_ref,
                root=component.get_root(),
            )
        except (InvalidReferenceError, AttributeError) as e:
            raise InvalidReferenceError(
                f"Could not resolve point reference '{self.point_ref}' from {component}: {e}"
            )

        if not isinstance(point, VoltageTuningPoint):
            raise TypeError(
                f"Reference '{self.point_ref}' resolved to {type(point).__name__}, "
                "expected VoltageTuningPoint"
            )

        return point

    def _get_point_name(self) -> str:
        """Extract point name from reference path.

        Returns:
            Full point name (e.g., "quantum_dot_0_idle")
        """
        point_ref_raw = object.__getattribute__(self, "__dict__").get("point_ref")
        if point_ref_raw is None:
            raise ValueError("point_ref is not set on this macro")

        parts = point_ref_raw.split("/")
        if not parts or parts[-1] == "":
            raise ValueError(f"Invalid point reference format: '{point_ref_raw}'")
        return parts[-1]

    def __call__(self, **overrides):
        """Invoke macro as callable (QUAM convention).

        Args:
            **overrides: Optional parameter overrides (hold_duration, ramp_duration, etc.)

        Returns:
            Result of apply() method
        """
        if not hasattr(self, "parent") or self.parent is None:
            raise ValueError(
                "Cannot execute macro: macro has no parent. "
                "Ensure macro is attached via component.macros['name'] = macro"
            )

        # Support 'duration' as alias for 'hold_duration'
        if "duration" in overrides and "hold_duration" not in overrides:
            overrides["hold_duration"] = overrides.pop("duration")

        return self.apply(**overrides)


@quam_dataclass
class StepPointMacro(BasePointMacro):
    """Macro for instantaneous voltage transition to registered point.

    Steps voltage instantly (limited by hardware) and holds for specified duration.

    Attributes:
        point_ref: Reference to VoltageTuningPoint
        hold_duration: Hold time at target voltage (nanoseconds)
        macro_type: Always "step"
    """

    macro_type: str = "step"

    @property
    def inferred_duration(self) -> Optional[float]:
        """Total duration of step operation (seconds)."""
        return self.hold_duration * 1e-9 if self.hold_duration is not None else None

    def apply(self, *args, hold_duration: Optional[int] = None):
        """Execute step operation.

        Args:
            hold_duration: Optional override for hold duration (nanoseconds)
        """
        duration = hold_duration if hold_duration is not None else self.hold_duration
        point_name = self._get_point_name()
        self.voltage_sequence.step_to_point(point_name, duration=duration)


@quam_dataclass
class RampPointMacro(BasePointMacro):
    """Macro for gradual voltage transition to registered point.

    Ramps voltage gradually over ramp_duration, then holds for hold_duration.
    Essential for adiabatic transitions.

    Attributes:
        point_ref: Reference to VoltageTuningPoint
        hold_duration: Hold time at target voltage (nanoseconds)
        ramp_duration: Gradual transition time (nanoseconds, default: 16)
        macro_type: Always "ramp"
    """

    macro_type: str = "ramp"
    ramp_duration: int = 16

    @property
    def inferred_duration(self) -> Optional[float]:
        """Total duration of ramp + hold (seconds)."""
        if self.ramp_duration is None or self.hold_duration is None:
            return None
        return (self.ramp_duration + self.hold_duration) * 1e-9

    def apply(
        self,
        *args,
        hold_duration: Optional[int] = None,
        ramp_duration: Optional[int] = None,
    ):
        """Execute ramp operation.

        Args:
            hold_duration: Optional override for hold duration (nanoseconds)
            ramp_duration: Optional override for ramp duration (nanoseconds)
        """
        ramp_ns = ramp_duration if ramp_duration is not None else self.ramp_duration
        hold_ns = hold_duration if hold_duration is not None else self.hold_duration
        point_name = self._get_point_name()
        self.voltage_sequence.ramp_to_point(
            point_name,
            ramp_duration=ramp_ns,
            duration=hold_ns,
        )
