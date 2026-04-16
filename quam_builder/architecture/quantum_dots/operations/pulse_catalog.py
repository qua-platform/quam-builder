"""Default pulse builders for quantum-dot channels.

Pulse defaults are materialized by ``PulseWirer`` during the
``wire_machine_macros()`` pass.  This module provides the channel-aware
helper builders used by that runtime pass.

Default pulse parameters
------------------------
Single-qubit XY drive pulse (on ``qubit.xy``):
    A single ``GaussianPulse`` named ``"gaussian"`` -- native length 1000
    samples / clock cycles (4 ns each), amplitude 1.0 (pi rotation
    reference), sigma 167 samples.
    This is the **single source of truth** for all XY rotations.

    Drive-type aware: IQ/MW channels get ``axis_angle=0.0``; a
    ``SingleChannel`` uses ``axis_angle=None``.

Readout pulse (on ``sensor_dot.readout_resonator``):
    ``SquareReadoutPulse`` -- native length 2000 samples / clock cycles
    (4 ns each), amplitude 1.0.
"""

from __future__ import annotations

from quam.components.channels import SingleChannel
from quam.components.pulses import SquareReadoutPulse
from quam_builder.architecture.quantum_dots.components.pulses import (
    ScalableGaussianPulse,
)
from quam_builder.architecture.quantum_dots.operations.names import DrivePulseName

__all__ = [
    "make_xy_pulse_factories",
    "make_readout_pulse",
]

_PULSE_LENGTH = 1000  # native samples / 4 ns clock cycles
_PULSE_AMP = 1.0
_SIGMA_RATIO = 1 / 6

_READOUT_LENGTH = 2000  # native samples / 4 ns clock cycles
_READOUT_AMP = 1.0


def make_xy_pulse_factories(drive_channel: object) -> dict[str, ScalableGaussianPulse]:
    """Build the default XY drive reference pulse for *drive_channel*.

    Returns a dict with a single ``"gaussian"`` pulse.  ``XYDriveMacro``
    scales amplitude for rotation angle and applies virtual-Z for axis,
    so only one calibrated pulse is needed.

    Drive-type awareness:
        - ``SingleChannel``: ``axis_angle=None`` (real-valued waveforms).
        - IQ/MW channels: ``axis_angle=0.0`` (hardware IQ mixing).

    Args:
        drive_channel: The XY drive channel instance.

    Returns:
        ``{"gaussian": ScalableGaussianPulse(...)}``.
    """
    is_single = isinstance(drive_channel, SingleChannel)
    axis_angle = None if is_single else 0.0

    return {
        DrivePulseName.GAUSSIAN.value: ScalableGaussianPulse(
            id=DrivePulseName.GAUSSIAN.value,
            length=_PULSE_LENGTH,
            amplitude=_PULSE_AMP,
            sigma_ratio=_SIGMA_RATIO,
            axis_angle=axis_angle,
        ),
    }


def make_readout_pulse() -> SquareReadoutPulse:
    """Build default readout pulse for sensor dot resonators.

    Returns:
        ``SquareReadoutPulse`` with id ``"readout"``, native length 2000
        samples / clock cycles, amplitude 1.0.
    """
    return SquareReadoutPulse(
        id="readout",
        length=_READOUT_LENGTH,
        amplitude=_READOUT_AMP,
    )
