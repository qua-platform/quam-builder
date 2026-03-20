"""Single-qubit default macros for quantum-dot qubits."""

# Framework macro base classes introduce deep inheritance chains by design.
# pylint: disable=too-many-ancestors

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from qm.qua import wait
from quam.components.macro import QubitMacro

from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    SingleQubitMacroName,
    VoltagePointName,
    X_NEG_90_ALIAS,
    Y_NEG_90_ALIAS,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    EmptyStateMacro,
    InitializeStateMacro,
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
    "ZNeg90Macro",
    "IdentityMacro",
]


def _quantize_ns(duration_ns: float) -> int:
    """Quantize nanoseconds to OPX 4 ns clock boundaries."""
    return max(int(round(duration_ns / 4.0)) * 4, 0)


def _compose_phase(base_phase: float, extra_phase: float | None) -> float:
    """Combine phase offsets across macro layers."""
    if extra_phase is None:
        return base_phase
    return base_phase + extra_phase


def _compose_amplitude_scale(
    base_scale: float,
    extra_scale: float | None,
) -> float | None:
    """Combine amplitude scales across macro layers.

    Returns ``None`` only when the composition is an identity scaling.
    """
    scale = base_scale if extra_scale is None else base_scale * extra_scale
    if extra_scale is None and math.isclose(scale, 1.0):
        return None
    return scale


class Initialize1QMacro(InitializeStateMacro, QubitMacro):
    """Initialize qubit by ramping to the `initialize` voltage point."""

    point: str = VoltagePointName.INITIALIZE.value


class Measure1QMacro(QubitMacro):
    """PSB measure macro for a single qubit.

    Navigates from the qubit to its preferred readout quantum dot,
    finds the corresponding QuantumDotPair, and delegates to the
    pair's measure macro which performs the full PSB readout chain.
    """

    def apply(self, **kwargs):
        """Perform PSB readout via the qubit's preferred readout dot pair.

        Returns:
            QUA boolean expression from the PSB state discrimination.
        """
        qubit = self.qubit
        preferred_dot_id = getattr(qubit, "preferred_readout_quantum_dot", None)
        if preferred_dot_id is None:
            raise ValueError(f"Qubit '{qubit.id}' has no preferred_readout_quantum_dot set.")

        own_dot = qubit.quantum_dot
        machine = qubit.machine
        pair_name = machine.find_quantum_dot_pair(own_dot.id, preferred_dot_id)
        if pair_name is None:
            raise ValueError(
                f"No QuantumDotPair found for dots '{own_dot.id}' and " f"'{preferred_dot_id}'."
            )

        qd_pair = machine.quantum_dot_pairs[pair_name]
        return qd_pair.macros[SingleQubitMacroName.MEASURE].apply(**kwargs)


class Empty1QMacro(EmptyStateMacro, QubitMacro):
    """Move qubit to the `empty` voltage point."""

    point: str = VoltagePointName.EMPTY.value


class XYDriveMacro(QubitMacro):
    """Canonical XY-drive macro with angle-to-drive-parameter conversion.

    The macro converts rotation angle to drive amplitude using a reference
    pulse (`x180` by default).  Duration is always the reference pulse
    duration — only amplitude is rescaled proportionally to the angle.

    Negative angles are represented as a +pi phase shift on the requested axis,
    so amplitude scaling is always computed from `abs(angle)`.

    The optional `phase` rotates the drive axis in the XY plane by applying a
    temporary frame rotation before the pulse and restoring it afterwards.
    """

    reference_pulse_name: str = DrivePulseName.GAUSSIAN.value
    reference_angle: float = float(np.pi)
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

        for candidate in (
            self.reference_pulse_name,
            DrivePulseName.GAUSSIAN,
            DrivePulseName.DRAG,
            SingleQubitMacroName.X_180,
            SingleQubitMacroName.X_90,
        ):
            if candidate in self.qubit.xy.operations:
                return candidate

        raise KeyError(
            f"No reference pulse found for qubit '{self.qubit.id}'. "
            "Expected one of: "
            f"'{self.reference_pulse_name}', "
            f"'{SingleQubitMacroName.X_180}', "
            f"'{SingleQubitMacroName.X_90}'."
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
        """Convert rotation angle to `(duration_ns, amplitude_scale)`.

        Duration is always the reference pulse duration (no stretching).
        Only amplitude is rescaled proportionally to the angle.
        """
        if self.reference_angle <= 0:
            raise ValueError("reference_angle must be positive.")

        relative = abs(angle) / self.reference_angle
        if math.isclose(relative, 0.0):
            return 0, 0.0

        base_duration_ns = self._reference_duration_ns(pulse_name)
        return base_duration_ns, relative

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
        """Play a phase-rotated XY drive pulse with compositional scaling.

        Runtime ``amplitude_scale`` multiplies the angle-derived scale from the
        reference pulse instead of replacing it.
        """
        # Accept 'duration' as alias so callers can write qubit.x180(duration=t)
        if pulse_duration is None:
            pulse_duration = kwargs.pop("duration", None)
        else:
            kwargs.pop("duration", None)

        target_angle = self.default_angle if angle is None else float(angle)
        if math.isclose(target_angle, 0.0):
            return None

        target_angle, phase = self._normalize_angle_sign_to_phase(target_angle, phase)
        resolved_pulse_name = self._resolve_pulse_name(pulse_name)
        auto_duration, auto_amplitude_scale = self._angle_to_drive_params(
            target_angle, resolved_pulse_name
        )

        duration_ns = auto_duration if pulse_duration is None else pulse_duration
        drive_scale = _compose_amplitude_scale(
            auto_amplitude_scale,
            amplitude_scale,
        )

        if not math.isclose(phase, 0.0):
            self.qubit.virtual_z(phase)

        self.qubit.voltage_sequence.step_to_voltages({}, duration=duration_ns)

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
        macro = self.qubit.macros.get(SingleQubitMacroName.XY_DRIVE)
        if macro is None:
            raise KeyError(f"Missing canonical macro '{SingleQubitMacroName.XY_DRIVE}' on qubit.")
        return macro

    @property
    def inferred_duration(self) -> float | None:
        """Infer runtime duration (seconds) for `default_angle`."""
        return self.inferred_duration_for_angle(self.default_angle)

    def inferred_duration_for_angle(self, angle: float) -> float | None:
        """Infer runtime duration (seconds) for a given angle via `xy_drive`."""
        macro = self._xy_drive_macro()
        infer_fn = getattr(macro, "inferred_duration_for_angle", None)
        return infer_fn(angle) if callable(infer_fn) else None

    def apply(self, angle: float | None = None, **kwargs):
        """Apply rotation around fixed XY axis by delegating to `xy_drive`."""
        target_angle = self.default_angle if angle is None else float(angle)
        phase = _compose_phase(self.phase, kwargs.pop("phase", None))
        runtime_amplitude_scale = kwargs.pop("amplitude_scale", None)
        call_kwargs = dict(kwargs)
        call_kwargs.update(
            angle=target_angle,
            phase=phase,
        )
        if runtime_amplitude_scale is not None:
            call_kwargs["amplitude_scale"] = runtime_amplitude_scale
        return self.qubit.macros[SingleQubitMacroName.XY_DRIVE].apply(
            **call_kwargs,
        )


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
    phase: float = 0.0

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
        extra_phase = kwargs.pop("phase", None)
        runtime_amplitude_scale = kwargs.pop("amplitude_scale", None)
        phase = _compose_phase(self.phase, extra_phase)
        call_kwargs = dict(kwargs)
        if extra_phase is not None or not math.isclose(self.phase, 0.0):
            call_kwargs["phase"] = phase
        if runtime_amplitude_scale is not None:
            call_kwargs["amplitude_scale"] = runtime_amplitude_scale
        return self.qubit.macros[self.axis_macro_name].apply(
            angle=target_angle,
            **call_kwargs,
        )


class X180Macro(_FixedAxisAngleMacro):
    """Apply 180-degree rotation around X axis via canonical `x` macro."""

    axis_macro_name: str = SingleQubitMacroName.X.value
    default_angle: float = float(np.pi)


class X90Macro(_FixedAxisAngleMacro):
    """Apply 90-degree rotation around X axis via canonical `x` macro."""

    axis_macro_name: str = SingleQubitMacroName.X.value
    default_angle: float = float(np.pi / 2)


class XNeg90Macro(_FixedAxisAngleMacro):
    """Apply -90-degree rotation around X axis via canonical `x` macro."""

    axis_macro_name: str = SingleQubitMacroName.X.value
    default_angle: float = float(-np.pi / 2)


class Y180Macro(_FixedAxisAngleMacro):
    """Apply 180-degree rotation around Y axis via canonical `y` macro."""

    axis_macro_name: str = SingleQubitMacroName.Y.value
    default_angle: float = float(np.pi)


class Y90Macro(_FixedAxisAngleMacro):
    """Apply 90-degree rotation around Y axis via canonical `y` macro."""

    axis_macro_name: str = SingleQubitMacroName.Y.value
    default_angle: float = float(np.pi / 2)


class YNeg90Macro(_FixedAxisAngleMacro):
    """Apply -90-degree rotation around Y axis via canonical `y` macro."""

    axis_macro_name: str = SingleQubitMacroName.Y.value
    default_angle: float = float(-np.pi / 2)


class Z180Macro(_FixedAxisAngleMacro):
    """Apply virtual 180-degree Z rotation via canonical `z` macro."""

    axis_macro_name: str = SingleQubitMacroName.Z.value
    default_angle: float = float(np.pi)


class Z90Macro(_FixedAxisAngleMacro):
    """Apply virtual 90-degree Z rotation via canonical `z` macro."""

    axis_macro_name: str = SingleQubitMacroName.Z.value
    default_angle: float = float(np.pi / 2)


class ZNeg90Macro(_FixedAxisAngleMacro):
    """Apply virtual -90-degree Z rotation via canonical `z` macro."""

    axis_macro_name: str = SingleQubitMacroName.Z.value
    default_angle: float = float(-np.pi / 2)


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
    VoltagePointName.INITIALIZE.value: Initialize1QMacro,
    VoltagePointName.MEASURE.value: Measure1QMacro,
    VoltagePointName.EMPTY.value: Empty1QMacro,
    SingleQubitMacroName.XY_DRIVE.value: XYDriveMacro,
    SingleQubitMacroName.X.value: XMacro,
    SingleQubitMacroName.Y.value: YMacro,
    SingleQubitMacroName.Z.value: ZMacro,
    SingleQubitMacroName.X_180.value: X180Macro,
    SingleQubitMacroName.X_90.value: X90Macro,
    SingleQubitMacroName.X_NEG_90.value: XNeg90Macro,
    X_NEG_90_ALIAS: XNeg90Macro,
    SingleQubitMacroName.Y_180.value: Y180Macro,
    SingleQubitMacroName.Y_90.value: Y90Macro,
    SingleQubitMacroName.Y_NEG_90.value: YNeg90Macro,
    Y_NEG_90_ALIAS: YNeg90Macro,
    SingleQubitMacroName.Z_180.value: Z180Macro,
    SingleQubitMacroName.Z_90.value: Z90Macro,
    SingleQubitMacroName.Z_NEG_90.value: ZNeg90Macro,
    SingleQubitMacroName.IDENTITY.value: IdentityMacro,
}
# Default single-qubit macro factories for ``LDQubit`` components.
