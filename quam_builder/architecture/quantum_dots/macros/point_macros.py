"""Voltage point macros for quantum dot operations.

This module provides macros for voltage point operations following QUAM's
Pulse → Macro → Operation pattern with reference-based serialization.
"""

from typing import TYPE_CHECKING

from quam import QuamComponent
from quam.core import quam_dataclass
from quam.core.macro.quam_macro import QuamMacro
from quam.utils import string_reference
from quam.utils.exceptions import InvalidReferenceError

from quam_builder.tools.qua_tools import DurationType, VoltageLevelType
from .composable_macros import SequenceMacro

if TYPE_CHECKING:
    from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
    from quam_builder.tools.voltage_sequence import VoltageSequence

__all__ = [
    "BasePointMacro",
    "StepPointMacro",
    "RampPointMacro",
    "SequenceMacro",
]


@quam_dataclass
class BasePointMacro(QuamMacro):
    """Base class for voltage point macros using reference-based pattern.

    Encapsulates operations on pre-defined voltage points stored in gate_set.macros.
    Stores references to points rather than concrete instances for serialization.

    Attributes:
        point_ref: Reference string to VoltageTuningPoint
            (e.g., "#./voltage_sequence/gate_set/macros/dot_0_idle")
        macro_type: Type identifier ('step', 'ramp', etc.)
    """

    point_ref: str | None = None
    macro_type: str = "base"

    @property
    def voltage_sequence(self) -> "VoltageSequence":
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
            ) from e

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

    def _get_default_duration(self) -> int | None:
        """Get default duration from the referenced VoltageTuningPoint.

        Returns:
            Duration in nanoseconds, or None if point cannot be resolved
        """
        try:
            point = self._resolve_point(self)
            return point.duration
        except (ValueError, InvalidReferenceError, TypeError):
            return None


@quam_dataclass
class StepPointMacro(BasePointMacro):
    """Macro for instantaneous voltage transition to registered point.

    Steps voltage instantly (limited by hardware) and holds for specified duration.

    Attributes:
        point_ref: Reference to VoltageTuningPoint
        macro_type: Always "step"
    """

    macro_type: str = "step"

    @property
    def inferred_duration(self) -> float | None:
        """Total duration of step operation (seconds)."""
        default_duration = self._get_default_duration()
        return default_duration * 1e-9 if default_duration is not None else None

    def apply(self, *args, duration: int | None = None, **kwargs):
        """Execute step operation.

        Args:
            duration: Override for hold duration (nanoseconds).
                If None, uses the VoltageTuningPoint's default duration.
        """
        if duration is None:
            duration = self._get_default_duration()
        point_name = self._get_point_name()
        self.voltage_sequence.step_to_point(point_name, duration=duration)


@quam_dataclass
class RampPointMacro(BasePointMacro):
    """Macro for gradual voltage transition to registered point.

    Ramps voltage gradually over ramp_duration, then holds for specified duration.
    Essential for adiabatic transitions.

    Attributes:
        point_ref: Reference to VoltageTuningPoint
        ramp_duration: Gradual transition time (nanoseconds, default: 16)
        macro_type: Always "ramp"
    """

    macro_type: str = "ramp"
    ramp_duration: int = 16

    @property
    def inferred_duration(self) -> float | None:
        """Total duration of ramp + hold (seconds)."""
        default_duration = self._get_default_duration()
        if self.ramp_duration is None or default_duration is None:
            return None
        return (self.ramp_duration + default_duration) * 1e-9

    def apply(
        self,
        *args,
        duration: int | None = None,
        ramp_duration: int | None = None,
        **kwargs,
    ):
        """Execute ramp operation.

        Args:
            duration: Override for hold duration (nanoseconds).
                If None, uses the VoltageTuningPoint's default duration.
            ramp_duration: Override for ramp duration (nanoseconds).
                If None, uses the macro's default ramp_duration.
        """
        if ramp_duration is None:
            ramp_duration = self.ramp_duration
        if duration is None:
            duration = self._get_default_duration()
        point_name = self._get_point_name()
        self.voltage_sequence.ramp_to_point(
            point_name,
            ramp_duration=ramp_duration,
            duration=duration,
        )
