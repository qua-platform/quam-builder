"""Single-qubit default macros for quantum-dot qubits.

Pulse family switching
----------------------
All single-qubit XY rotations are parameterised by a **pulse family**
(``"gaussian"``, ``"square"``, ``"kaiser"``, ``"hermite"``, or ``"drag"``).  The active family is
stored in ``XYDriveMacro.pulse_family`` and determines which operation
from ``qubit.xy.operations`` is played.  Operations follow the naming
convention ``{family}_{gate}`` (e.g. ``"kaiser_x180"``).

Changing ``machine.pulse_family`` (and propagating via
``machine.set_pulse_family()``) switches **all** macros simultaneously.

Two families of single-qubit rotations
---------------------------------------
* **Dedicated-pulse macros** (``X180Macro``, ``X90Macro``, ``XNeg90Macro``,
  ``Y180Macro``, ``Y90Macro``, ``YNeg90Macro``, and ``XYDriveMacro``)
  each play their own calibrated operation at its stored amplitude.
  ``XYDriveMacro`` plays ``{family}_x180``, the same pulse as ``x180``.
  They do not accept ``angle``.  A phase shift is ``qubit.z(...)``
  followed by the gate.
* **Canonical macros** (``XMacro``, ``YMacro``, ``ZMacro``).  ``XMacro``
  plays ``{family}_x180`` and ``YMacro`` plays ``{family}_y180``, with
  amplitude scaled by ``angle / pi``.  A negative angle is a negative
  amplitude scale.  Omitting ``angle`` is a π rotation, the same gate as
  ``x180`` or ``y180``.
  ``ZMacro`` is a frame rotation with no pulse.  That rotation stays on
  the element; it is the gate.  ``Z180Macro``, ``Z90Macro``, and
  ``ZNeg90Macro`` are the same call at a fixed angle and do not accept
  ``angle``.

By default the pulse plays at its calibrated ``length``.  Pass
``duration`` (in clock cycles, 1 cycle = 4 ns) to override it at runtime,
e.g. ``qubit.x180(duration=t)`` with ``t`` a QUA variable.  This forwards
to QUA's ``play(duration=…)`` and is the most efficient way to sweep drive
length (time-Rabi, Rabi chevron) on the OPX.

``inferred_duration`` reports the calibrated ``length`` in seconds
(``length * 1e-9``) and ignores a runtime ``duration`` override.  When
sweeping the duration, size any surrounding voltage hold from the swept
value rather than from ``inferred_duration``.
"""

# Framework macro base classes introduce deep inheritance chains by design.
# pylint: disable=too-many-ancestors

from __future__ import annotations

import dataclasses
from typing import ClassVar

import numpy as np

from quam.components.macro import QubitMacro
from quam.core import quam_dataclass
from quam.core.macro import QuamMacro
from quam.utils import string_reference

from quam_builder.architecture.quantum_dots.operations.names import (
    X_NEG_90_ALIAS,
    Y_NEG_90_ALIAS,
    DrivePulseName,
    SingleQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS

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


def _reference_anchor(raw: object, field: str) -> str | None:
    """Operation name a QuAM reference points at, or ``None`` if *raw* is stored."""
    if not string_reference.is_reference(raw):
        return None
    parts = [part for part in str(raw).split("/") if part not in {"#", "#.", "#..", ".", ".."}]
    if len(parts) >= 2 and parts[-1] == field:
        return parts[-2]
    return parts[-1] if parts else str(raw)


def _require_stored_field(pulse_name: str, pulse, field: str) -> None:
    """Reject an update of *field* when the pulse stores a reference there."""
    anchor = _reference_anchor(pulse.get_raw_value(field), field)
    if anchor is not None:
        raise ValueError(f"{pulse_name}.{field} references {anchor}. Update that pulse instead.")


def _compose_amplitude_scale(
    base_scale: float,
    extra_scale: float | None,
) -> float | None:
    """Combine amplitude scales across macro layers.

    Returns ``None`` only when the composition is an identity scaling.
    """
    scale = base_scale if extra_scale is None else base_scale * extra_scale
    if extra_scale is None and np.isclose(scale, 1.0):
        return None
    return scale


def _resolve_qubit_pair(qubit):
    """Resolve the LDQubitPair for a qubit via preferred_readout_quantum_dot.

    Iterates ``machine.qubit_pairs`` to find a pair where one member is
    *qubit* and the other member's quantum dot matches
    ``preferred_readout_quantum_dot``.

    Raises:
        ValueError: If preferred_readout_quantum_dot is not set or pair not found.
    """
    preferred_dot_id = getattr(qubit, "preferred_readout_quantum_dot", None)
    if preferred_dot_id is None:
        raise ValueError(f"Qubit '{qubit.id}' has no preferred_readout_quantum_dot set.")
    machine = qubit.machine
    for pair in machine.qubit_pairs.values():
        qc, qt = pair.qubit_control, pair.qubit_target
        if qc is qubit and qt.quantum_dot.id == preferred_dot_id:
            return pair
        if qt is qubit and qc.quantum_dot.id == preferred_dot_id:
            return pair
    raise ValueError(
        f"No QubitPair found for qubit '{qubit.id}' with "
        f"preferred_readout_quantum_dot '{preferred_dot_id}'."
    )


def _state_macro_field_names(state_macro_cls: type) -> frozenset[str]:
    """Dataclass field names on *state_macro_cls* excluding QuamMacro base fields."""
    base = {f.name for f in dataclasses.fields(QuamMacro)}
    return frozenset(f.name for f in dataclasses.fields(state_macro_cls)) - base


@quam_dataclass
class Initialize1QMacro(QubitMacro):
    """Initialize qubit by delegating to the QuantumDotPair's initialize macro."""

    _CANONICAL_MACRO_NAME = "initialize"

    def _resolve_canonical_macro(self):
        pair = _resolve_qubit_pair(self.qubit)
        return pair.macros[self._CANONICAL_MACRO_NAME]

    @property
    def inferred_duration(self) -> float | None:
        try:
            return self._resolve_canonical_macro().inferred_duration
        except (ValueError, KeyError):
            return None

    def update(self, **kwargs) -> None:
        self._resolve_canonical_macro().update(**kwargs)

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        # Let qubit.initialize() default to driving/conditioning on itself when
        # the underlying initialize macro supports heralded arguments.
        if kwargs.get("qubit_name") is None:
            kwargs["qubit_name"] = self.qubit.name
        return self._resolve_canonical_macro().apply(**kwargs)


@quam_dataclass
class Measure1QMacro(QubitMacro):
    """PSB measure macro for a single qubit.

    Navigates from the qubit to its preferred readout quantum dot,
    finds the corresponding QuantumDotPair, and delegates to the
    pair's measure macro which performs the full PSB readout chain.
    """

    _CANONICAL_MACRO_NAME = "measure"

    def _resolve_canonical_macro(self):
        pair = _resolve_qubit_pair(self.qubit)
        return pair.macros[self._CANONICAL_MACRO_NAME]

    @property
    def inferred_duration(self) -> float | None:
        try:
            return self._resolve_canonical_macro().inferred_duration
        except (ValueError, KeyError):
            return None

    def update(self, **kwargs) -> None:
        self._resolve_canonical_macro().update(**kwargs)

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        return self._resolve_canonical_macro().apply(**kwargs)


@quam_dataclass
class Empty1QMacro(QubitMacro):
    """Move qubit to empty by delegating to the QuantumDotPair's empty macro."""

    _CANONICAL_MACRO_NAME = "empty"

    def _resolve_canonical_macro(self):
        pair = _resolve_qubit_pair(self.qubit)
        return pair.macros[self._CANONICAL_MACRO_NAME]

    @property
    def inferred_duration(self) -> float | None:
        try:
            return self._resolve_canonical_macro().inferred_duration
        except (ValueError, KeyError):
            return None

    def update(self, **kwargs) -> None:
        self._resolve_canonical_macro().update(**kwargs)

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        return self._resolve_canonical_macro().apply(**kwargs)


@quam_dataclass
class XYDriveMacro(QubitMacro):
    """Base macro for XY-plane rotations with switchable pulse families.

    The active pulse envelope is determined by ``pulse_family`` combined
    with a per-subclass ``_gate_suffix``.  This base macro plays
    ``{family}_x180``.  Changing ``pulse_family`` (e.g. from
    ``"gaussian"`` to ``"kaiser"``) switches the envelope used by all XY
    macros simultaneously.
    """

    pulse_family: str = DrivePulseName.GAUSSIAN.value

    _gate_suffix: ClassVar[str] = "_x180"
    _scales_with_angle: ClassVar[bool] = False

    @property
    def pulse_name(self) -> str:
        """Operation name resolved from the active family and gate suffix."""
        return f"{self.pulse_family}{self._gate_suffix}"

    @property
    def reference_pulse_name(self) -> str:
        """Operation this macro plays. Same value as ``pulse_name``."""
        return self.pulse_name

    @property
    def pulse(self):
        """Return the operation this macro plays."""
        return self.qubit.xy.operations[self.pulse_name]

    @property
    def inferred_duration(self) -> float | None:
        """Length of the operation this macro plays, in seconds."""
        return self.qubit.xy.operations[self.pulse_name].length * 1e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def update(
        self,
        *,
        amplitude_scale: float | None = None,
        duration: int | None = None,
        frequency: float | None = None,
        frequency_offset: float | None = None,
    ) -> None:
        """Persistently update the pulse this macro plays.

        ``amplitude_scale`` multiplies that pulse's stored amplitude.
        ``duration`` sets its length in nanoseconds. When the pulse has
        ``sigma_ratio``, sigma is set from that ratio.

        A length, amplitude, or sigma that is a QuAM reference is left
        unchanged. The call raises ``ValueError`` and names the operation
        that stores the value, before any field is written. A custom
        subclass whose pulse stores those fields updates that pulse.

        ``frequency`` and ``frequency_offset`` set
        ``qubit.larmor_frequency`` from any XY macro. Changes are stored
        on the QuAM objects and kept by ``machine.save``.

        Args:
            amplitude_scale: Multiply the played pulse's stored amplitude
                by this factor.
            duration: Set the played pulse's length in nanoseconds.
            frequency: Set ``qubit.larmor_frequency`` to this absolute
                value (Hz). When both this and *frequency_offset* are
                passed, this value is the one stored.
            frequency_offset: Add this offset (Hz) to the current
                ``qubit.larmor_frequency``.
        """
        played = self.qubit.xy.operations[self.pulse_name]
        if amplitude_scale is not None:
            _require_stored_field(self.pulse_name, played, "amplitude")
        if duration is not None:
            _require_stored_field(self.pulse_name, played, "length")
            if hasattr(played, "sigma_ratio"):
                _require_stored_field(self.pulse_name, played, "sigma")

        if amplitude_scale is not None:
            played.amplitude = played.amplitude * amplitude_scale

        if duration is not None:
            played.length = duration
            if hasattr(played, "sigma_ratio"):
                played.sigma = duration * played.sigma_ratio

        if frequency is not None:
            self.qubit.larmor_frequency = float(frequency)

        elif frequency_offset is not None:
            self.qubit.larmor_frequency = float(self.qubit.larmor_frequency + frequency_offset)

    def apply(
        self,
        amplitude_scale: float | None = None,
        duration=None,
        angle: float | None = None,
    ):
        """Play this macro's operation.

        ``angle`` (radians, ``x``/``y`` only) is the rotation: the π pulse
        is scaled by ``angle / π``. ``amplitude_scale`` is an extra one-shot
        multiplier on that play. A frame shift is ``z()``.
        """
        if self._scales_with_angle:
            effective_angle = np.pi if angle is None else angle
            amplitude_scale = _compose_amplitude_scale(effective_angle / np.pi, amplitude_scale)
        elif angle is not None:
            raise TypeError(
                f"{type(self).__name__} does not accept 'angle'. "
                "Use x() or y() for an arbitrary angle."
            )
        self.qubit.xy.play(
            pulse_name=self.pulse_name, amplitude_scale=amplitude_scale, duration=duration
        )


@quam_dataclass
class XMacro(XYDriveMacro):
    """Canonical, arbitrary-angle rotation around X.

    Plays the calibrated ``{family}_x180`` pulse with amplitude scaled by
    ``angle / pi``. A negative angle is a negative amplitude scale.
    Omitting ``angle`` is a π rotation, the same gate as ``x180``.
    """

    _gate_suffix: ClassVar[str] = "_x180"
    _scales_with_angle: ClassVar[bool] = True


@quam_dataclass
class YMacro(XYDriveMacro):
    """Canonical, arbitrary-angle rotation around Y.

    Plays the calibrated ``{family}_y180`` pulse, whose axis is already Y,
    with amplitude scaled by ``angle / pi``. A negative angle is a negative
    amplitude scale. Omitting ``angle`` is a π rotation, the same gate as
    ``y180``.
    """

    _gate_suffix: ClassVar[str] = "_y180"
    _scales_with_angle: ClassVar[bool] = True


@quam_dataclass
class ZMacro(QubitMacro):
    """Canonical virtual-Z rotation macro.

    ``angle`` is the rotation in radians. Omitting it uses
    ``default_angle`` (π). The rotation stays on the element. Fixed-angle
    subclasses set ``_accepts_angle`` to false and reject a passed angle.
    """

    default_angle: float = float(np.pi)
    _accepts_angle: ClassVar[bool] = True

    @property
    def inferred_duration(self) -> float:
        """Virtual-Z is frame-only and therefore has zero duration."""
        return 0.0

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, angle: float | None = None):
        """Apply a virtual-Z rotation."""
        if angle is not None and not self._accepts_angle:
            raise TypeError(
                f"{type(self).__name__} does not accept 'angle'. "
                "Use z() for an arbitrary virtual-Z rotation."
            )
        target_angle = self.default_angle if angle is None else angle
        self.qubit.virtual_z(target_angle)


@quam_dataclass
class X180Macro(XYDriveMacro):
    """Apply 180-degree rotation around X axis via the dedicated pi pulse."""

    _gate_suffix: ClassVar[str] = "_x180"

    axis_macro_name: str = SingleQubitMacroName.X.value


@quam_dataclass
class X90Macro(XYDriveMacro):
    """Apply 90-degree rotation around X axis."""

    _gate_suffix: ClassVar[str] = "_x90"

    axis_macro_name: str = SingleQubitMacroName.X.value


@quam_dataclass
class XNeg90Macro(XYDriveMacro):
    """Apply -90-degree rotation around X axis via dedicated pulse with axis_angle=pi."""

    _gate_suffix: ClassVar[str] = "_x_neg90"

    axis_macro_name: str = SingleQubitMacroName.X.value


@quam_dataclass
class Y180Macro(XYDriveMacro):
    """Apply 180-degree rotation around Y axis via dedicated pulse with axis_angle=pi/2."""

    _gate_suffix: ClassVar[str] = "_y180"

    axis_macro_name: str = SingleQubitMacroName.Y.value


@quam_dataclass
class Y90Macro(XYDriveMacro):
    """Apply 90-degree rotation around Y axis via dedicated pulse with axis_angle=pi/2."""

    _gate_suffix: ClassVar[str] = "_y90"

    axis_macro_name: str = SingleQubitMacroName.Y.value


@quam_dataclass
class YNeg90Macro(XYDriveMacro):
    """Apply -90-degree rotation around Y axis via dedicated pulse with axis_angle=-pi/2."""

    _gate_suffix: ClassVar[str] = "_y_neg90"

    axis_macro_name: str = SingleQubitMacroName.Y.value


@quam_dataclass
class Z180Macro(ZMacro):
    """Virtual π rotation around Z. Does not accept ``angle``."""

    axis_macro_name: str = SingleQubitMacroName.Z.value
    default_angle: float = float(np.pi)
    _accepts_angle: ClassVar[bool] = False


@quam_dataclass
class Z90Macro(ZMacro):
    """Virtual π/2 rotation around Z. Does not accept ``angle``."""

    axis_macro_name: str = SingleQubitMacroName.Z.value
    default_angle: float = float(np.pi / 2)
    _accepts_angle: ClassVar[bool] = False


@quam_dataclass
class ZNeg90Macro(ZMacro):
    """Virtual -π/2 rotation around Z. Does not accept ``angle``."""

    axis_macro_name: str = SingleQubitMacroName.Z.value
    default_angle: float = float(-np.pi / 2)
    _accepts_angle: ClassVar[bool] = False


@quam_dataclass
class IdentityMacro(QubitMacro):
    """Identity operation implemented as wait."""

    duration: int = DEFAULTS.misc.identity_duration

    @property
    def inferred_duration(self) -> float:
        """Return configured wait duration in seconds."""
        return self.duration * 1e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, duration: int | None = None, **kwargs):
        duration = self.duration if duration is None else duration
        self.qubit.idle(duration=duration)


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
