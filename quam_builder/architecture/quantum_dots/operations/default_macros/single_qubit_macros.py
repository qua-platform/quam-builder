"""Single-qubit default macros for quantum-dot qubits."""

# Framework macro base classes introduce deep inheritance chains by design.
# pylint: disable=too-many-ancestors

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from qm.qua import wait
from quam.components.macro import QubitMacro

from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    EmptyStateMacro,
    InitializeStateMacro,
    MeasureStateMacro,
)

__all__ = [
    "SINGLE_QUBIT_MACROS",
    "Initialize1QMacro",
    "Measure1QMacro",
    "Empty1QMacro",
    "XYDriveMacro",
    "XMacro",
    "YMacro",
    "ZMacro",
    "X180Macro",
    "X90Macro",
    "XNeg90Macro",
    "Y180Macro",
    "Y90Macro",
    "YNeg90Macro",
    "Z180Macro",
    "Z90Macro",
    "IdentityMacro",
]


def _quantize_ns(duration_ns: float) -> int:
    """Quantize nanoseconds to OPX 4 ns clock boundaries."""
    return max(int(round(duration_ns / 4.0)) * 4, 0)


class Initialize1QMacro(InitializeStateMacro, QubitMacro):
    """Initialize qubit by ramping to the `initialize` voltage point."""


class Measure1QMacro(MeasureStateMacro, QubitMacro):
    """Move qubit to the `measure` voltage point."""


class Empty1QMacro(EmptyStateMacro, QubitMacro):
    """Move qubit to the `empty` voltage point."""


class XYDriveMacro(QubitMacro):
    """Canonical XY-drive macro with angle-to-drive-parameter conversion.

    The macro converts rotation angle to drive amplitude and duration using a
    reference pulse (`x180` by default):

    - `|angle| <= pi`: scale amplitude while keeping the reference duration.
    - `|angle| > pi`: saturate amplitude at `max_amplitude_scale` and stretch
      duration proportionally.

    Negative angles are represented as a +pi phase shift on the requested axis,
    so amplitude scaling is always computed from `abs(angle)`.

    The optional `phase` rotates the drive axis in the XY plane by applying a
    temporary frame rotation before the pulse and restoring it afterwards.
    """

    reference_pulse_name: str = "x180"
    reference_angle: float = float(np.pi)
    max_amplitude_scale: float = 1.0
    default_angle: float = float(np.pi)

    def _resolve_pulse_name(self, pulse_name: str | None) -> str:
        if self.qubit.xy is None:
            raise ValueError(f"Qubit '{self.qubit.id}' has no XY drive configured.")

        if pulse_name is not None:
            if pulse_name not in self.qubit.xy.operations:
                raise KeyError(
                    f"Pulse operation '{pulse_name}' is not defined on qubit '{self.qubit.id}'."
                )
            return pulse_name

        for candidate in (self.reference_pulse_name, "x180", "x90"):
            if candidate in self.qubit.xy.operations:
                return candidate

        raise KeyError(
            f"No reference pulse found for qubit '{self.qubit.id}'. "
            f"Expected one of: '{self.reference_pulse_name}', 'x180', 'x90'."
        )

    def _reference_duration_ns(self, pulse_name: str) -> int | None:
        pulse = self.qubit.xy.operations[pulse_name]
        length = getattr(pulse, "length", None)
        return length if isinstance(length, int) else None

    def _angle_to_drive_params(
        self,
        angle: float,
        pulse_name: str,
    ) -> tuple[int | None, float]:
        """Convert rotation angle to `(duration_ns, amplitude_scale)`."""
        if self.reference_angle <= 0:
            raise ValueError("reference_angle must be positive.")

        relative = abs(angle) / self.reference_angle
        if math.isclose(relative, 0.0):
            return 0, 0.0

        amplitude_scale = min(relative, self.max_amplitude_scale)

        base_duration_ns = self._reference_duration_ns(pulse_name)
        if base_duration_ns is None:
            return None, amplitude_scale

        stretch = relative / amplitude_scale
        duration_ns = _quantize_ns(base_duration_ns * stretch)
        return duration_ns, amplitude_scale

    @staticmethod
    def _normalize_angle_sign_to_phase(angle: float, phase: float) -> tuple[float, float]:
        """Encode negative-angle rotations as positive angle + pi phase offset."""
        if angle < 0:
            return abs(angle), phase + float(np.pi)
        return angle, phase

    def inferred_duration_for_angle(self, angle: float) -> float | None:
        """Infer runtime duration (seconds) for a given rotation angle."""
        try:
            pulse_name = self._resolve_pulse_name(None)
            duration_ns, _ = self._angle_to_drive_params(abs(angle), pulse_name)
        except Exception:  # pragma: no cover - defensive
            return None

        return duration_ns * 1e-9 if isinstance(duration_ns, int) else None

    @property
    def inferred_duration(self) -> float | None:
        """Infer runtime duration (seconds) for `default_angle`."""
        return self.inferred_duration_for_angle(self.default_angle)

    def apply(
        self,
        angle: float | None = None,
        phase: float = 0.0,
        pulse_name: str | None = None,
        pulse_duration: Optional[int] = None,
        amplitude_scale: float | None = None,
        restore_frame: bool = True,
        **kwargs,
    ):
        """Play a phase-rotated XY drive pulse with angle-based scaling."""
        target_angle = self.default_angle if angle is None else float(angle)
        if math.isclose(target_angle, 0.0):
            return None

        target_angle, phase = self._normalize_angle_sign_to_phase(target_angle, phase)
        resolved_pulse_name = self._resolve_pulse_name(pulse_name)
        auto_duration, auto_amplitude_scale = self._angle_to_drive_params(
            target_angle, resolved_pulse_name
        )

        duration_ns = auto_duration if pulse_duration is None else pulse_duration
        drive_scale = auto_amplitude_scale if amplitude_scale is None else amplitude_scale

        if not math.isclose(phase, 0.0):
            self.qubit.virtual_z(phase)

        self.qubit.play_xy_pulse(
            resolved_pulse_name,
            pulse_duration=duration_ns,
            amplitude_scale=drive_scale,
            **kwargs,
        )

        if restore_frame and not math.isclose(phase, 0.0):
            self.qubit.virtual_z(-phase)


class _AxisRotationMacro(QubitMacro):
    """Canonical axis-rotation macro delegating to `xy_drive`."""

    default_angle: float = float(np.pi)
    phase: float = 0.0

    def _xy_drive_macro(self):
        macro = self.qubit.macros.get("xy_drive")
        if macro is None:
            raise KeyError("Missing canonical macro 'xy_drive' on qubit.")
        return macro

    @property
    def inferred_duration(self) -> float | None:
        """Infer runtime duration (seconds) for `default_angle`."""
        macro = self._xy_drive_macro()
        infer_fn = getattr(macro, "inferred_duration_for_angle", None)
        return infer_fn(self.default_angle) if callable(infer_fn) else None

    def apply(self, angle: float | None = None, **kwargs):
        """Apply rotation around fixed XY axis by delegating to `xy_drive`."""
        target_angle = self.default_angle if angle is None else float(angle)
        return self.qubit.call_macro("xy_drive", angle=target_angle, phase=self.phase, **kwargs)


class XMacro(_AxisRotationMacro):
    """Canonical X-axis rotation macro."""

    default_angle: float = float(np.pi)
    phase: float = 0.0


class YMacro(_AxisRotationMacro):
    """Canonical Y-axis rotation macro."""

    default_angle: float = float(np.pi)
    phase: float = float(np.pi / 2)


class ZMacro(QubitMacro):
    """Canonical virtual-Z rotation macro."""

    default_angle: float = float(np.pi)

    @property
    def inferred_duration(self) -> float:
        """Virtual-Z is frame-only and therefore has zero duration."""
        return 0.0

    def apply(self, angle: float | None = None, **kwargs):
        """Apply virtual-Z rotation for requested angle."""
        target_angle = self.default_angle if angle is None else float(angle)
        self.qubit.virtual_z(target_angle)


class _FixedAxisAngleMacro(QubitMacro):
    """Fixed-angle wrapper that delegates to canonical `x`, `y`, or `z` macro."""

    axis_macro_name: str
    default_angle: float

    @property
    def inferred_duration(self) -> float | None:
        axis_macro = self.qubit.macros.get(self.axis_macro_name)
        if axis_macro is None:
            return None

        infer_fn = getattr(axis_macro, "inferred_duration_for_angle", None)
        if callable(infer_fn):
            return infer_fn(self.default_angle)

        duration = getattr(axis_macro, "inferred_duration", None)
        return float(duration) if isinstance(duration, (int, float)) else None

    def apply(self, angle: float | None = None, **kwargs):
        target_angle = self.default_angle if angle is None else float(angle)
        return self.qubit.call_macro(self.axis_macro_name, angle=target_angle, **kwargs)


class X180Macro(_FixedAxisAngleMacro):
    """Apply 180-degree rotation around X axis via canonical `x` macro."""

    axis_macro_name: str = "x"
    default_angle: float = float(np.pi)


class X90Macro(_FixedAxisAngleMacro):
    """Apply 90-degree rotation around X axis via canonical `x` macro."""

    axis_macro_name: str = "x"
    default_angle: float = float(np.pi / 2)


class XNeg90Macro(_FixedAxisAngleMacro):
    """Apply -90-degree rotation around X axis via canonical `x` macro."""

    axis_macro_name: str = "x"
    default_angle: float = float(-np.pi / 2)


class Y180Macro(_FixedAxisAngleMacro):
    """Apply 180-degree rotation around Y axis via canonical `y` macro."""

    axis_macro_name: str = "y"
    default_angle: float = float(np.pi)


class Y90Macro(_FixedAxisAngleMacro):
    """Apply 90-degree rotation around Y axis via canonical `y` macro."""

    axis_macro_name: str = "y"
    default_angle: float = float(np.pi / 2)


class YNeg90Macro(_FixedAxisAngleMacro):
    """Apply -90-degree rotation around Y axis via canonical `y` macro."""

    axis_macro_name: str = "y"
    default_angle: float = float(-np.pi / 2)


class Z180Macro(_FixedAxisAngleMacro):
    """Apply virtual 180-degree Z rotation via canonical `z` macro."""

    axis_macro_name: str = "z"
    default_angle: float = float(np.pi)


class Z90Macro(_FixedAxisAngleMacro):
    """Apply virtual 90-degree Z rotation via canonical `z` macro."""

    axis_macro_name: str = "z"
    default_angle: float = float(np.pi / 2)


class IdentityMacro(QubitMacro):
    """Identity operation implemented as wait."""

    duration: int = 16

    @property
    def inferred_duration(self) -> float:
        """Return configured wait duration in seconds."""
        return self.duration * 1e-9

    def apply(self, duration: int | None = None, **kwargs):
        """Implement identity as a quantized wait on qubit channels."""
        duration_ns = self.duration if duration is None else duration
        if duration_ns < 0:
            raise ValueError("Identity duration must be non-negative.")
        duration_ns = max(0, int(round(duration_ns / 4.0)) * 4)

        # Qubit.wait also issues qua.wait but expects clock cycles. Use it when available.
        if hasattr(self.qubit, "wait"):
            self.qubit.wait(duration_ns // 4)
        else:
            wait(duration_ns // 4)


SINGLE_QUBIT_MACROS = {
    "initialize": Initialize1QMacro,
    "measure": Measure1QMacro,
    "empty": Empty1QMacro,
    "xy_drive": XYDriveMacro,
    "x": XMacro,
    "y": YMacro,
    "z": ZMacro,
    "x180": X180Macro,
    "x90": X90Macro,
    "x_neg90": XNeg90Macro,
    "-x90": XNeg90Macro,
    "y180": Y180Macro,
    "y90": Y90Macro,
    "y_neg90": YNeg90Macro,
    "-y90": YNeg90Macro,
    "z180": Z180Macro,
    "z90": Z90Macro,
    "I": IdentityMacro,
}
# Default single-qubit macro factories for ``LDQubit`` components.
