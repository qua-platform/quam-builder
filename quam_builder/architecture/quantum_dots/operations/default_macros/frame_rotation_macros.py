"""X and Y macros that select the rotation axis with a frame rotation.

These macros play the calibrated X pulse (``{family}_x180`` or
``{family}_x90``) and put the axis into the drive frame. Before the
pulse the frame is rotated by ``-axis_phase``; after the pulse it is
rotated back by ``+axis_phase``. The net frame is unchanged.

``axis_phase`` is radians. X is ``0`` and emits no rotation. Y is
``π/2``. The calls are ``qua.frame_rotation_2pi`` with the phase in
turns (``axis_phase / 2π``), the same conversion as
``LDQubit.virtual_z``. In time order the sequence is
``R_z(-axis_phase)``, the X pulse, ``R_z(+axis_phase)``, which is a
rotation about the axis at ``axis_phase``.

Y gates play the X pulse of the same angle. ``y`` and ``y180`` play
``{family}_x180``. ``y90`` and ``y_neg90`` play ``{family}_x90``.
``x_neg90`` plays ``{family}_x90`` at phase ``π``. ``update()`` writes
that played pulse.

Register them in place of the dedicated-pulse X and Y macros with
:class:`~quam_builder.architecture.quantum_dots.operations.macro_catalog.FrameRotationXYMacroCatalog`.
"""

# pylint: disable=too-many-ancestors
from __future__ import annotations

from typing import ClassVar

import numpy as np
from qm import qua
from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    XYDriveMacro,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    X_NEG_90_ALIAS,
    Y_NEG_90_ALIAS,
    SingleQubitMacroName,
)

__all__ = [
    "FRAME_ROTATION_XY_MACROS",
    "FrameRotationXYMacro",
    "FrameXMacro",
    "FrameYMacro",
    "FrameX180Macro",
    "FrameX90Macro",
    "FrameXNeg90Macro",
    "FrameY180Macro",
    "FrameY90Macro",
    "FrameYNeg90Macro",
]


def _phase_turns(phase_rad: float) -> float:
    """Convert a radian axis phase to the turns ``frame_rotation_2pi`` takes."""
    return float(phase_rad) / (2.0 * np.pi)


@quam_dataclass
class FrameRotationXYMacro(XYDriveMacro):
    """Play the X pulse between opposite ``frame_rotation_2pi`` calls.

    ``axis_phase`` is the rotation-axis angle in radians. A zero phase
    is an X rotation and does not touch the frame. Any other phase
    rotates the frame by ``-axis_phase`` before the pulse and by
    ``+axis_phase`` after it.
    """

    axis_phase: float = 0.0

    def apply(
        self,
        amplitude_scale: float | None = None,
        duration=None,
        angle: float | None = None,
    ):
        """Play the X pulse on the axis given by ``axis_phase``."""
        if angle is not None and not self._scales_with_angle:
            raise TypeError(
                f"{type(self).__name__} does not accept 'angle'. "
                "Use x() or y() for an arbitrary angle."
            )
        turns = _phase_turns(self.axis_phase)
        element = self.qubit.xy.name
        if not np.isclose(turns, 0.0):
            qua.frame_rotation_2pi(-turns, element)
        super().apply(amplitude_scale=amplitude_scale, duration=duration, angle=angle)
        if not np.isclose(turns, 0.0):
            qua.frame_rotation_2pi(turns, element)


@quam_dataclass
class FrameXMacro(FrameRotationXYMacro):
    """Arbitrary-angle rotation about X.

    Plays ``{family}_x180`` scaled by ``angle / π``. Omitting ``angle``
    is a π rotation. The axis phase is 0, so the frame is not rotated.
    """

    axis_phase: float = 0.0
    _gate_suffix: ClassVar[str] = "_x180"
    _scales_with_angle: ClassVar[bool] = True


@quam_dataclass
class FrameYMacro(FrameRotationXYMacro):
    """Arbitrary-angle rotation about Y.

    Plays ``{family}_x180`` scaled by ``angle / π``, between frame
    rotations of ``-π/2`` and ``+π/2``. Omitting ``angle`` is a π
    rotation about Y.
    """

    axis_phase: float = float(np.pi / 2)
    _gate_suffix: ClassVar[str] = "_x180"
    _scales_with_angle: ClassVar[bool] = True


@quam_dataclass
class FrameX180Macro(FrameRotationXYMacro):
    """π rotation about X. Plays ``{family}_x180`` and does not take ``angle``."""

    axis_phase: float = 0.0
    _gate_suffix: ClassVar[str] = "_x180"
    axis_macro_name: str = SingleQubitMacroName.X.value


@quam_dataclass
class FrameX90Macro(FrameRotationXYMacro):
    """π/2 rotation about X. Plays ``{family}_x90`` and does not take ``angle``."""

    axis_phase: float = 0.0
    _gate_suffix: ClassVar[str] = "_x90"
    axis_macro_name: str = SingleQubitMacroName.X.value


@quam_dataclass
class FrameXNeg90Macro(FrameRotationXYMacro):
    """-π/2 rotation about X.

    Plays ``{family}_x90`` between frame rotations of ``-π`` and ``+π``.
    Does not take ``angle``.
    """

    axis_phase: float = float(np.pi)
    _gate_suffix: ClassVar[str] = "_x90"
    axis_macro_name: str = SingleQubitMacroName.X.value


@quam_dataclass
class FrameY180Macro(FrameRotationXYMacro):
    """π rotation about Y.

    Plays ``{family}_x180`` between frame rotations of ``-π/2`` and
    ``+π/2``. Does not take ``angle``.
    """

    axis_phase: float = float(np.pi / 2)
    _gate_suffix: ClassVar[str] = "_x180"
    axis_macro_name: str = SingleQubitMacroName.Y.value


@quam_dataclass
class FrameY90Macro(FrameRotationXYMacro):
    """π/2 rotation about Y.

    Plays ``{family}_x90`` between frame rotations of ``-π/2`` and
    ``+π/2``. Does not take ``angle``.
    """

    axis_phase: float = float(np.pi / 2)
    _gate_suffix: ClassVar[str] = "_x90"
    axis_macro_name: str = SingleQubitMacroName.Y.value


@quam_dataclass
class FrameYNeg90Macro(FrameRotationXYMacro):
    """-π/2 rotation about Y.

    Plays ``{family}_x90`` between frame rotations of ``+π/2`` and
    ``-π/2``. Does not take ``angle``.
    """

    axis_phase: float = float(-np.pi / 2)
    _gate_suffix: ClassVar[str] = "_x90"
    axis_macro_name: str = SingleQubitMacroName.Y.value


FRAME_ROTATION_XY_MACROS = {
    SingleQubitMacroName.X.value: FrameXMacro,
    SingleQubitMacroName.Y.value: FrameYMacro,
    SingleQubitMacroName.X_180.value: FrameX180Macro,
    SingleQubitMacroName.X_90.value: FrameX90Macro,
    SingleQubitMacroName.X_NEG_90.value: FrameXNeg90Macro,
    X_NEG_90_ALIAS: FrameXNeg90Macro,
    SingleQubitMacroName.Y_180.value: FrameY180Macro,
    SingleQubitMacroName.Y_90.value: FrameY90Macro,
    SingleQubitMacroName.Y_NEG_90.value: FrameYNeg90Macro,
    Y_NEG_90_ALIAS: FrameYNeg90Macro,
}
# X/Y macro factories that select the axis with ``frame_rotation_2pi``.
