"""Default pulse builders for quantum-dot channels.

Pulse defaults are materialized by ``PulseWirer`` during the
``wire_machine_macros()`` pass.  This module provides the channel-aware
helper builders used by that runtime pass.

All default parameter values (lengths, amplitudes, sigma ratio) are
imported from :mod:`~quam_builder.architecture.quantum_dots.defaults`.
"""

from __future__ import annotations
from typing import Optional

import numpy as np
from quam.components.channels import SingleChannel
from quam.components.pulses import SquareReadoutPulse

from quam_builder.architecture.quantum_dots.components.pulses import (
    ScalableDragPulse,
    ScalableGaussianPulse,
    ScalableHermitePulse,
    ScalableKaiserPulse,
    ScalableSquarePulse,
)
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    TwoQubitMacroName,
)

__all__ = [
    "PULSE_FAMILIES",
    "make_xy_pulse_factories",
    "make_readout_pulse",
]

PULSE_FAMILIES = {
    DrivePulseName.GAUSSIAN.value: ScalableGaussianPulse,
    DrivePulseName.SQUARE.value: ScalableSquarePulse,
    DrivePulseName.KAISER.value: ScalableKaiserPulse,
    DrivePulseName.HERMITE.value: ScalableHermitePulse,
    DrivePulseName.DRAG.value: ScalableDragPulse,
}

_AXIS_VARIANTS = {
    "x_neg90": {"ref_anchor": "x90", "axis_angle": np.pi},
    "y180": {"ref_anchor": "x180", "axis_angle": np.pi / 2},
    "y90": {"ref_anchor": "x90", "axis_angle": np.pi / 2},
    "y_neg90": {"ref_anchor": "x90", "axis_angle": -np.pi / 2},
}


def _make_family_pulses(
    family: str,
    pulse_cls: type,
    is_single: bool,
) -> dict:
    """Generate the 6 standard gate operations for a single pulse family."""
    axis_angle_base = None if is_single else 0.0
    x90_name = f"{family}_x90"
    x180_name = f"{family}_x180"

    common_kwargs = {}
    if pulse_cls in (ScalableGaussianPulse, ScalableHermitePulse, ScalableDragPulse):
        common_kwargs["sigma_ratio"] = DEFAULTS.xy_pulse.sigma_ratio

    x90_amp = DEFAULTS.xy_pulse.amplitude
    x180_amp = DEFAULTS.xy_pulse.amplitude * 2

    ops = {
        x90_name: pulse_cls(
            id=x90_name,
            amplitude=x90_amp,
            axis_angle=axis_angle_base,
            length=DEFAULTS.xy_pulse.length,
            **common_kwargs,
        ),
        x180_name: pulse_cls(
            id=x180_name,
            amplitude=x180_amp,
            axis_angle=axis_angle_base,
            length=DEFAULTS.xy_pulse.length,
            **common_kwargs,
        ),
    }

    for gate_suffix, spec in _AXIS_VARIANTS.items():
        op_name = f"{family}_{gate_suffix}"
        anchor_name = f"{family}_{spec['ref_anchor']}"

        ref_kwargs = {
            "length": f"#../{anchor_name}/length",
            "amplitude": f"#../{anchor_name}/amplitude",
        }
        if pulse_cls is ScalableGaussianPulse:
            ref_kwargs["sigma"] = f"#../{anchor_name}/sigma"
            ref_kwargs["sigma_ratio"] = f"#../{anchor_name}/sigma_ratio"
        elif pulse_cls is ScalableHermitePulse:
            ref_kwargs["sigma_ratio"] = f"#../{anchor_name}/sigma_ratio"
            ref_kwargs["hermite_coeff"] = f"#../{anchor_name}/hermite_coeff"
        elif pulse_cls is ScalableDragPulse:
            ref_kwargs["sigma_ratio"] = f"#../{anchor_name}/sigma_ratio"
            ref_kwargs["drag_coefficient"] = f"#../{anchor_name}/drag_coefficient"

        ops[op_name] = pulse_cls(
            id=op_name,
            axis_angle=None if is_single else spec["axis_angle"],
            **ref_kwargs,
        )

    return ops


def make_xy_pulse_factories(drive_channel: object) -> dict:
    """Build the default XY drive pulses for *drive_channel*.

    Generates operations for all registered pulse families (Gaussian,
    Square, Kaiser).  Each family produces 6 operations following the
    naming convention ``{family}_{gate}``:

    - ``{family}_x90``  -- calibration anchor (x90 amplitude)
    - ``{family}_x180`` -- pi pulse (2x amplitude)
    - ``{family}_x_neg90``, ``{family}_y180``, ``{family}_y90``,
      ``{family}_y_neg90`` -- axis variants referencing anchor params

    Drive-type awareness:
        - ``SingleChannel``: ``axis_angle=None`` (real-valued waveforms).
        - IQ/MW channels: ``axis_angle`` set per gate (hardware IQ mixing).

    Args:
        drive_channel: The XY drive channel instance.

    Returns:
        Dict mapping operation names to pulse instances for all families,
        plus a ``"cz"`` entry.
    """
    is_single = isinstance(drive_channel, SingleChannel)

    all_ops: dict = {}
    for family, pulse_cls in PULSE_FAMILIES.items():
        all_ops.update(_make_family_pulses(family, pulse_cls, is_single))

    all_ops[TwoQubitMacroName.CZ.value] = ScalableGaussianPulse(
        id="cz",
        length=DEFAULTS.xy_pulse.length,
        amplitude=DEFAULTS.xy_pulse.amplitude,
        sigma_ratio=DEFAULTS.xy_pulse.sigma_ratio,
        axis_angle=None if is_single else 0.0,
    )

    all_ops[DrivePulseName.CROT.value] = ScalableGaussianPulse(
        id="crot",
        length=DEFAULTS.xy_pulse.length,
        amplitude=DEFAULTS.xy_pulse.amplitude,
        sigma_ratio=DEFAULTS.xy_pulse.sigma_ratio,
        axis_angle=None if is_single else 0.0,
    )

    return all_ops


def make_readout_pulse(dot_pair_name: Optional[str] = None) -> SquareReadoutPulse:
    """Build default readout pulse for sensor dot resonators.

    Returns:
        ``SquareReadoutPulse`` with id ``"readout"``, length from
        ``DEFAULTS.readout.length`` (nanoseconds), amplitude from
        ``DEFAULTS.readout.amplitude``.
    """
    return SquareReadoutPulse(
        id="readout" if dot_pair_name is None else f"readout_{dot_pair_name}",
        length=DEFAULTS.readout.length,
        amplitude=DEFAULTS.readout.amplitude,
    )
