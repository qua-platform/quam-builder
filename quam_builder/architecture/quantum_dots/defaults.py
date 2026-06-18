"""Centralized default parameters for the quantum-dot architecture.

This module is the **single source of truth** for every default parameter
value used by macros, pulses, and builders.  Other modules import the
module-level ``DEFAULTS`` instance instead of defining their own constants.

To customize defaults, modify ``DEFAULTS`` **before** importing builder or
macro modules — field defaults on macro classes are evaluated at import
time (when the class is first defined).

Example::

    from quam_builder.architecture.quantum_dots.defaults import (
        DEFAULTS, XYPulseDefaults, ReadoutDefaults,
    )

    DEFAULTS.xy_pulse = XYPulseDefaults(length=500, amplitude=0.25)
    DEFAULTS.readout = ReadoutDefaults(length=3000, amplitude=0.35)

    # Now import and build — modules will pick up the modified values.
    from quam_builder.builder.quantum_dots import build_quam
    ...
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class XYPulseDefaults:
    """Default parameters for the XY drive Gaussian pulse."""

    length: int = 1000
    """Pulse length in nanoseconds (samples at 1 GS/s) → 1 µs."""

    amplitude: float = 0.25
    """Normalized amplitude (pi-rotation reference)."""

    sigma_ratio: float = 1 / 6
    """Sigma = length × sigma_ratio."""


@dataclass
class ReadoutDefaults:
    """Default parameters for the sensor readout pulse."""

    frequency: float = 400e6
    """Default readout intermediate frequency in Hz."""

    length: int = 5000
    """Pulse length in nanoseconds (samples at 1 GS/s) → 1 µs."""

    amplitude: float = 0.15
    """Normalized amplitude."""


@dataclass
class FrequencyDefaults:
    """Default frequency parameters for qubit XY drives."""

    larmor_frequency: float | None = 5e9
    """Qubit resonance frequency in Hz.  ``None`` means the builder
    falls back to ``LO + intermediate_frequency``."""

    lo_frequency: float | None = 5e9
    """Default LO/upconverter frequency in Hz."""

    intermediate_frequency: float = 0
    """Default XY-drive intermediate frequency in Hz."""


@dataclass
class StateMacroDefaults:
    """Default timing for state macros (initialize, measure, empty)."""

    ramp_duration: int = 524
    """Ramp time in ns."""

    hold_duration: int = 524
    """Hold time in ns for macros that still source it (e.g. voltage-balanced round-trips).

    Canonical :class:`~quam_builder.architecture.quantum_dots.operations.default_macros.state_macros.EmptyStateMacro`
    and :class:`~quam_builder.architecture.quantum_dots.operations.default_macros.state_macros.InitializeStateMacro`
    default ``hold_duration`` to ``None`` so the :class:`~quam_builder.architecture.quantum_dots.components.gate_set.VoltageTuningPoint`
    duration applies unless the macro field is set.
    """

    buffer_duration: int = 524
    """Buffer time in ns.  ``None`` means no extra buffer."""

    point_duration: int = 524
    """Default voltage-point duration in ns."""


@dataclass
class ExchangeDefaults:
    """Default timing for exchange macros."""

    ramp_duration: int = 524
    """Ramp time in ns."""

    wait_duration: int = 524
    """Wait/hold time at the exchange point in ns."""

    cz_duration: int = 524
    """Default hold time at the CZ voltage point in ns."""


@dataclass
class VoltagePulseDefaults:
    """Default voltage pulse parameters for gate channels."""

    direct_amplitude: float = 0.25
    """Square pulse amplitude for direct voltage outputs."""

    amplified_amplitude: float = 1.25
    """Square pulse amplitude for amplified voltage outputs."""


@dataclass
class QdacDefaults:
    """Default QDAC helper parameters."""

    triangle_span_V: float = 0.2
    """Default span for QDAC triangle-wave helper in volts."""


@dataclass
class MiscDefaults:
    """Miscellaneous defaults."""

    sticky_duration: int = 16
    """StickyChannelAddon duration in ns."""

    identity_duration: int = 16
    """IdentityMacro wait duration in ns."""


@dataclass
class QubitDefaults:
    """Default parameters for LD qubit components."""

    thermalization_time_factor: int = 5
    """Multiplier applied to T1 for thermal reset wait time."""

    fallback_t1: float = 10e-6
    """Fallback T1 in seconds when a qubit has no calibrated T1."""


@dataclass
class QDDefaults:
    """Top-level container for all quantum-dot architecture defaults.

    Instantiate with no arguments for architecture defaults.
    Override only the groups/fields that differ for your lab.
    """

    xy_pulse: XYPulseDefaults = field(default_factory=XYPulseDefaults)
    readout: ReadoutDefaults = field(default_factory=ReadoutDefaults)
    frequency: FrequencyDefaults = field(default_factory=FrequencyDefaults)
    state_macro: StateMacroDefaults = field(default_factory=StateMacroDefaults)
    exchange: ExchangeDefaults = field(default_factory=ExchangeDefaults)
    voltage_pulse: VoltagePulseDefaults = field(default_factory=VoltagePulseDefaults)
    qdac: QdacDefaults = field(default_factory=QdacDefaults)
    qubit: QubitDefaults = field(default_factory=QubitDefaults)
    misc: MiscDefaults = field(default_factory=MiscDefaults)


DEFAULTS = QDDefaults()
