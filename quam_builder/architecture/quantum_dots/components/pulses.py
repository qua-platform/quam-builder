"""Custom pulse classes for quantum-dot architectures."""

from __future__ import annotations

import numpy as np
from quam.components.pulses import GaussianPulse
from quam.core import quam_dataclass

__all__ = ["ScalableGaussianPulse"]


@quam_dataclass
class ScalableGaussianPulse(GaussianPulse):
    """Gaussian pulse whose sigma is always derived from ``length * sigma_ratio``.

    This avoids having to manually rescale sigma when the pulse duration
    changes.  Only ``length`` and ``sigma_ratio`` are independent
    parameters; ``sigma`` is kept in sync automatically.

    Args:
        amplitude (float): Peak amplitude of the pulse in volts.
        length (int): Duration of the pulse in ns (samples).
        sigma_ratio (float): Ratio ``sigma / length``.  Default ``1/6``
            matches the conventional ``sigma = length / 6``.
        axis_angle (float, optional): IQ axis angle in radians.
        subtracted (bool): If True, subtract the edge value so the
            waveform starts and ends at zero.  Default True.
    """

    sigma: float = None
    sigma_ratio: float = 1 / 6

    def __post_init__(self):
        super().__post_init__()
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
