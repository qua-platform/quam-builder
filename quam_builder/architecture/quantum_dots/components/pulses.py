"""Custom pulse classes for quantum-dot architectures."""

from __future__ import annotations

import numpy as np
from scipy.special import i0  # pylint: disable=no-name-in-module

from quam.components.pulses import GaussianPulse, Pulse
from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.defaults import DEFAULTS

__all__ = [
    "ScalableGaussianPulse",
    "ScalableSquarePulse",
    "ScalableKaiserPulse",
    "ScalableHermitePulse",
    "ScalableDragPulse",
]


@quam_dataclass
class ScalableGaussianPulse(GaussianPulse):
    """Gaussian pulse whose sigma is always derived from ``length * sigma_ratio``.

    This avoids having to manually rescale sigma when the pulse duration
    changes.  Only ``length`` and ``sigma_ratio`` are independent
    parameters; ``sigma`` is kept in sync automatically.

    Args:
        amplitude (float): Peak amplitude of the pulse in volts.
        length (int): Pulse length in nanoseconds (samples at 1 GS/s).
            Must be a multiple of 4.
        sigma_ratio (float): Ratio ``sigma / length``.  Default ``1/6``
            matches the conventional ``sigma = length / 6``.
        axis_angle (float, optional): IQ axis angle in radians.
        subtracted (bool): If True, subtract the edge value so the
            waveform starts and ends at zero.  Default True.
    """

    sigma: float = None
    sigma_ratio: float = DEFAULTS.xy_pulse.sigma_ratio

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.length, str) and not isinstance(self.sigma_ratio, str):
            self.sigma = self.length * self.sigma_ratio

    def waveform_function(self):
        sigma = self.length * self.sigma_ratio
        t = np.arange(self.length, dtype=int)
        center = (self.length - 1) / 2
        waveform = self.amplitude * np.exp(-((t - center) ** 2) / (2 * sigma**2))

        if self.subtracted:
            waveform = waveform - waveform[-1]

        if self.axis_angle is not None:
            waveform = waveform * np.exp(1j * self.axis_angle)

        return waveform


@quam_dataclass
class ScalableSquarePulse(Pulse):
    """Constant-amplitude (rectangular) pulse envelope for XY drive channels.

    Produces a flat-top waveform of duration ``length`` at the given
    ``amplitude``.  Supports IQ channels via ``axis_angle``.

    Args:
        amplitude (float): Pulse amplitude in volts.
        length (int): Pulse length in nanoseconds (samples at 1 GS/s).
            Must be a multiple of 4.
        axis_angle (float, optional): IQ axis angle in radians.  ``None``
            produces a real-valued waveform (for SingleChannel drives).
    """

    length: int = DEFAULTS.xy_pulse.length
    amplitude: float = DEFAULTS.xy_pulse.amplitude
    axis_angle: float = None

    def waveform_function(self):
        waveform = self.amplitude * np.ones(self.length)
        if self.axis_angle is not None:
            waveform = waveform * np.exp(1j * self.axis_angle)
        return waveform


@quam_dataclass
class ScalableKaiserPulse(Pulse):
    """Kaiser-window pulse envelope for XY drive channels.

    The Kaiser window suppresses off-resonant spectral components
    compared to rectangular or Gaussian envelopes, reducing crosstalk
    in multi-qubit systems (Wu et al., arXiv:2507.11918).

    The waveform is peak-normalized: the maximum sample equals
    ``amplitude``.  This gives the same calibration workflow as
    Gaussian and Square pulses — fix duration, sweep amplitude, and
    measure Rabi oscillations to find pi and pi/2 amplitudes.

    Args:
        amplitude (float): Peak amplitude of the pulse in volts.
        length (int): Pulse length in nanoseconds (samples at 1 GS/s).
            Must be a multiple of 4.
        beta (float): Kaiser shape parameter.  Fixed at 8.0 per
            arXiv:2507.11918.
        axis_angle (float, optional): IQ axis angle in radians.  ``None``
            produces a real-valued waveform (for SingleChannel drives).
    """

    length: int = DEFAULTS.xy_pulse.length
    amplitude: float = DEFAULTS.xy_pulse.amplitude
    beta: float = 8.0
    axis_angle: float = None

    def waveform_function(self):
        n = np.arange(self.length, dtype=float)
        center = (self.length - 1) / 2.0
        arg = self.beta * np.sqrt(
           1.0 - ((n - center) / center) ** 2
        )
        window = i0(arg) / i0(self.beta)
        window = window / np.max(window)
        waveform = self.amplitude * window
        if self.axis_angle is not None:
            waveform = waveform * np.exp(1j * self.axis_angle)
        return waveform


@quam_dataclass
class ScalableHermitePulse(Pulse):
    """Hermite-Gaussian pulse envelope for XY drive channels.

    The envelope is a Gaussian multiplied by a second-order Hermite-like
    polynomial term controlled by ``hermite_coeff``:

        exp(-x^2 / 2) * (1 - hermite_coeff * x^2)

    where ``x = (t - center) / sigma``. The waveform is peak-normalized so
    the maximum absolute sample equals ``amplitude``.

    Args:
        amplitude (float): Peak amplitude of the pulse in volts.
        length (int): Pulse length in nanoseconds (samples at 1 GS/s).
            Must be a multiple of 4.
        sigma_ratio (float): Ratio ``sigma / length`` used to derive
            ``sigma`` from ``length``.
        hermite_coeff (float): Weight of the Hermite polynomial term.
        axis_angle (float, optional): IQ axis angle in radians.
    """

    length: int = DEFAULTS.xy_pulse.length
    amplitude: float = DEFAULTS.xy_pulse.amplitude
    sigma: float = None
    sigma_ratio: float = DEFAULTS.xy_pulse.sigma_ratio
    hermite_coeff: float = 0.5
    axis_angle: float = None

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.length, str) and not isinstance(self.sigma_ratio, str):
            self.sigma = self.length * self.sigma_ratio

    def waveform_function(self):
        sigma = self.length * self.sigma_ratio
        t = np.arange(self.length, dtype=float)
        center = (self.length - 1) / 2.0
        x = (t - center) / sigma

        base = np.exp(-(x**2) / 2.0)
        hermite_shape = 1.0 - self.hermite_coeff * (x**2)
        waveform = base * hermite_shape

        peak = np.max(np.abs(waveform))
        if peak > 0:
            waveform = self.amplitude * (waveform / peak)
        else:
            waveform = np.zeros_like(waveform)

        if self.axis_angle is not None:
            waveform = waveform * np.exp(1j * self.axis_angle)
        return waveform


@quam_dataclass
class ScalableDragPulse(Pulse):
    """DRAG pulse envelope for XY drive channels.

    Implements a Gaussian in-phase envelope plus a derivative quadrature:

        I(x) = exp(-x^2 / 2)
        Q(x) = drag_coefficient * (-x * exp(-x^2 / 2))

    with ``x = (t - center) / sigma`` and ``sigma = length * sigma_ratio``.

    For IQ drives (``axis_angle`` set), the pulse is emitted as ``I + iQ``
    and rotated by ``exp(i * axis_angle)``.  For SingleChannel drives
    (``axis_angle=None``), only the in-phase Gaussian component is used.
    """

    length: int = DEFAULTS.xy_pulse.length
    amplitude: float = DEFAULTS.xy_pulse.amplitude
    sigma: float = None
    sigma_ratio: float = DEFAULTS.xy_pulse.sigma_ratio
    drag_coefficient: float = 0.5
    axis_angle: float = None

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.length, str) and not isinstance(self.sigma_ratio, str):
            self.sigma = self.length * self.sigma_ratio

    def waveform_function(self):
        sigma = self.length * self.sigma_ratio
        t = np.arange(self.length, dtype=float)
        center = (self.length - 1) / 2.0
        x = (t - center) / sigma

        gaussian = np.exp(-(x**2) / 2.0)
        gaussian = gaussian / np.max(gaussian)
        i_envelope = self.amplitude * gaussian

        derivative = -x * gaussian
        deriv_peak = np.max(np.abs(derivative))
        if deriv_peak > 0:
            derivative = derivative / deriv_peak
        q_envelope = self.amplitude * self.drag_coefficient * derivative

        if self.axis_angle is None:
            return i_envelope

        waveform = i_envelope + 1j * q_envelope
        return waveform * np.exp(1j * self.axis_angle)
