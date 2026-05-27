"""Default pulse builders for quantum-dot channels.

Unlike macro defaults, pulse defaults are currently materialized directly in
``macro_engine.wiring._ensure_default_pulses()``. This module only provides the
channel-aware helper builders used by that runtime pass.

Default pulse parameters
------------------------
Single-qubit XY drive pulse (on ``qubit.xy``):
    A single ``GaussianPulse`` named ``"gaussian"`` — length 1000 ns,
    amplitude 1.0 (π rotation reference), sigma 167 ns.
    This is the **single source of truth** for all XY rotations.
    The ``XYDriveMacro`` scales amplitude for different rotation angles
    and applies virtual-Z frame rotations for the rotation axis (X/Y),
    so only one reference pulse is needed.

    Drive-type aware: IQ/MW channels get ``axis_angle=0.0`` for hardware
    mixing; ``SingleChannel`` (``XYDriveSingle``) uses ``axis_angle=None``.

Readout pulse (on ``sensor_dot.readout_resonator``):
    ``SquareReadoutPulse`` — length 2000 ns, amplitude 0.1.

Usage::

    from quam_builder.architecture.quantum_dots.operations.component_pulse_catalog import (
        _make_xy_pulse_factories,
        _make_readout_pulse,
    )

    pulses = _make_xy_pulse_factories(qubit.xy)
    readout = _make_readout_pulse()
"""

from __future__ import annotations

from quam.components.channels import SingleChannel
from quam.components.pulses import SquareReadoutPulse

from quam_builder.architecture.quantum_dots.components.pulses import ScalableGaussianPulse
from quam_builder.architecture.quantum_dots.operations.names import DrivePulseName

__all__: list[str] = []

# Default single-qubit XY pulse parameters
_PULSE_LENGTH = 1000  # ns
_PULSE_AMP = 1.0  # normalized (macro stores calibrated scaling)
_SIGMA_RATIO = 1 / 6

# Default readout pulse parameters
_READOUT_LENGTH = 2000  # ns
_READOUT_AMP = 1.0


def _make_xy_pulse_factories(drive_channel):
    """Build default XY drive reference pulse for an XY drive channel.

    Returns a dict with a single ``"gaussian"`` pulse — the reference
    envelope used by ``XYDriveMacro`` for all single-qubit rotations.  The macro
    handles amplitude scaling (for rotation angle) and virtual-Z frame rotation
    (for rotation axis), so only one calibrated pulse is needed.

    Users can register additional pulse types (e.g. ``"drag"``) and
    point ``XYDriveMacro.reference_pulse_name`` at them to switch the
    envelope used for all gates.

    Drive-type awareness:
        - ``SingleChannel`` (``XYDriveSingle``): ``axis_angle=None`` — real-valued
          waveforms only, rotation axis encoded via virtual-Z.
        - IQ/MW channels: ``axis_angle=0.0`` — hardware IQ mixing; rotation
          axis is set by virtual-Z frame rotation in the macro.

    Args:
        drive_channel: The XY drive channel instance. Checked with
            ``isinstance(drive_channel, SingleChannel)`` to determine pulse type.

    Returns:
        Dict with one entry: ``{"gaussian": GaussianPulse(...)}``.

    Example::

        pulses = _make_xy_pulse_factories(qubit.xy)
        qubit.xy.operations.update(pulses)
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


def _make_readout_pulse():
    """Build default readout pulse for sensor dot resonators.

    Returns:
        ``SquareReadoutPulse`` with id ``"readout"``, length 2000 ns,
        amplitude 0.1.
    """
    return SquareReadoutPulse(
        id="readout",
        length=_READOUT_LENGTH,
        amplitude=_READOUT_AMP,
    )
