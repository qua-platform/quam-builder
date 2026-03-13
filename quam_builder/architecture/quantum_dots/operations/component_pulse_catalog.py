"""Default pulse catalog for quantum-dot component types.

Parallel to :mod:`~quam_builder.architecture.quantum_dots.operations.component_macro_catalog`,
this module provides idempotent registration of default pulse factories for
core quantum-dot component types (``LDQubit``, ``SensorDot``).

Default pulse parameters
------------------------
Single-qubit XY drive pulse (on ``qubit.xy``):
    A single ``GaussianPulse`` named ``"gaussian"`` — length 1000 ns,
    amplitude 0.2 (π rotation reference), sigma 167 ns.
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
        register_default_component_pulse_factories,
        _make_xy_pulse_factories,
        _make_readout_pulse,
    )

    # Register all built-in defaults (idempotent):
    register_default_component_pulse_factories()

    # Or build pulse dicts directly for a specific drive channel:
    pulses = _make_xy_pulse_factories(qubit.xy)
    readout = _make_readout_pulse()
"""

from __future__ import annotations

from quam.components.channels import SingleChannel
from quam.components.pulses import GaussianPulse, SquareReadoutPulse

from quam_builder.architecture.quantum_dots.operations.names import DrivePulseName
from quam_builder.architecture.quantum_dots.operations.pulse_registry import (
    register_component_pulse_factories,
)

_REGISTERED = False

__all__ = [
    "register_default_component_pulse_factories",
]

# Default single-qubit XY pulse parameters
_PULSE_LENGTH = 1000  # ns
_PULSE_AMP = 0.2  # 180° amplitude
_SIGMA = _PULSE_LENGTH / 6

# Default readout pulse parameters
_READOUT_LENGTH = 2000  # ns
_READOUT_AMP = 0.1


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
        DrivePulseName.GAUSSIAN.value: GaussianPulse(
            id=DrivePulseName.GAUSSIAN.value,
            length=_PULSE_LENGTH,
            amplitude=_PULSE_AMP,
            sigma=_SIGMA,
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


def register_default_component_pulse_factories() -> None:
    """Register built-in pulse factories for core quantum-dot component types.

    This function is idempotent — calling it multiple times has no effect after
    the first registration.  It is called automatically by
    :func:`~quam_builder.architecture.quantum_dots.macro_engine.wiring._ensure_default_pulses`
    during ``wire_machine_macros()``.

    Registration is intentionally centralized here (rather than in component
    ``__post_init__``) to keep default behavior decoupled from component class
    definitions.  Actual pulse instances are created at wiring time by
    ``_ensure_default_pulses``, which inspects each drive channel's type to
    select the correct ``axis_angle``.

    Registered component types:
        - ``LDQubit``: placeholder (actual XY pulses created at wiring time
          based on drive channel type).
        - ``SensorDot``: placeholder (readout pulse created at wiring time).
    """
    global _REGISTERED
    if _REGISTERED:
        return

    from quam_builder.architecture.quantum_dots.qubit import LDQubit
    from quam_builder.architecture.quantum_dots.components.sensor_dot import SensorDot

    # LDQubit: XY drive pulses (actual instances created at wiring time
    # since drive type must be inspected)
    register_component_pulse_factories(LDQubit, {})

    # SensorDot: readout pulse
    register_component_pulse_factories(SensorDot, {})

    _REGISTERED = True


def _reset_registration() -> None:
    """Reset global registration state. FOR TESTING ONLY."""
    global _REGISTERED
    _REGISTERED = False
