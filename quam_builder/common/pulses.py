from abc import ABC
import warnings
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from quam.core import quam_dataclass
from quam.components.pulses import Pulse, BaseReadoutPulse

__all__ = [
    "ReadoutPulse",
    "SquarePulse",
    "SquareReadoutPulse",
    "GaussianPulse",
    "FlatTopGaussianPulse",
    "FlatTopCosinePulse",
    "ConstantReadoutPulse",
]


@quam_dataclass
class ReadoutPulse(BaseReadoutPulse, ABC):
    """QUAM abstract base component for most readout pulses.

    This class is a subclass of `BaseReadoutPulse` and should be used for most readout
    pulses. It provides a default implementation of the `integration_weights_function`
    method, which is suitable for most cases.

    Args:
        length (int): The length of the pulse in samples.
        digital_marker (str, list, optional): The digital marker to use for the pulse.
            Default is "ON".
        integration_weights (list[float], list[tuple[float, int]], optional): The
            integration weights, can be either
            - a list of floats (one per sample), the length must match the pulse length
            - a list of tuples of (weight, length) pairs, the sum of the lengths must
              match the pulse length
        integration_weights_angle (float, optional): The rotation angle for the
            integration weights in radians.
    """

    integration_weights: Union[List[float], List[Tuple[float, int]]] = (
        "#./default_integration_weights"
    )
    integration_weights_angle: float = 0

    @property
    def default_integration_weights(self) -> List[Tuple[float, int]]:
        return [(1, self.length)]

    def integration_weights_function(self) -> List[Tuple[Union[complex, float], int]]:
        from qualang_tools.config import convert_integration_weights

        phase = np.exp(1j * self.integration_weights_angle)

        if isinstance(self.integration_weights[0], float):
            integration_weights = convert_integration_weights(self.integration_weights)
        else:
            integration_weights = self.integration_weights

        return {
            "real": [(phase.real * w, l) for w, l in integration_weights],
            "imag": [(phase.imag * w, l) for w, l in integration_weights],
            "minus_real": [(-phase.real * w, l) for w, l in integration_weights],
            "minus_imag": [(-phase.imag * w, l) for w, l in integration_weights],
        }


@quam_dataclass
class SquarePulse(Pulse):
    """Square pulse QUAM component.

    Args:
        length (int): The length of the pulse in samples.
        digital_marker (str, list, optional): The digital marker to use for the pulse.
        amplitude (float): The amplitude of the pulse in volts.
        axis_angle (float, optional): IQ axis angle of the output pulse in radians.
            If None (default), the pulse is meant for a single channel or the I port
                of an IQ channel
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).
    """

    amplitude: float
    axis_angle: float = None

    def waveform_function(self):
        waveform = self.amplitude

        if self.axis_angle is not None:
            waveform = waveform * np.exp(1j * self.axis_angle)
        return waveform


@quam_dataclass
class SquareReadoutPulse(ReadoutPulse, SquarePulse):
    """QUAM component for a square readout pulse.

    Args:
        length (int): The length of the pulse in samples.
        digital_marker (str, list, optional): The digital marker to use for the pulse.
            Default is "ON".
        amplitude (float): The constant amplitude of the pulse.
        axis_angle (float, optional): IQ axis angle of the output pulse in radians.
            If None (default), the pulse is meant for a single channel or the I port
                of an IQ channel
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).
        integration_weights (list[float], list[tuple[float, int]], optional): The
            integration weights, can be either
            - a list of floats (one per sample), the length must match the pulse length
            - a list of tuples of (weight, length) pairs, the sum of the lengths must
              match the pulse length
        integration_weights_angle (float, optional): The rotation angle for the
            integration weights in radians.
    """

    ...


@quam_dataclass
class ConstantReadoutPulse(SquareReadoutPulse):
    def __post_init__(self) -> None:
        warnings.warn(
            "ConstantReadoutPulse is deprecated. Use SquareReadoutPulse instead.",
            DeprecationWarning,
        )
        return super().__post_init__()


@quam_dataclass
class GaussianPulse(Pulse):
    """Gaussian pulse QUAM component.

    Args:
        amplitude (float): The amplitude of the pulse in volts.
        length (int): The length of the pulse in samples.
        sigma (float): The standard deviation of the gaussian pulse.
            Should generally be less than half the length of the pulse.
        axis_angle (float, optional): IQ axis angle of the output pulse in radians.
            If None (default), the pulse is meant for a single channel or the I port
                of an IQ channel
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).
        subtracted (bool): If true, returns a subtracted Gaussian, such that the first
            and last points will be at 0 volts. This reduces high-frequency components
            due to the initial and final points offset. Default is true.
    """

    amplitude: float
    length: int
    sigma: float
    axis_angle: float = None
    subtracted: bool = True

    def waveform_function(self):
        t = np.arange(self.length, dtype=int)
        center = (self.length - 1) / 2
        waveform = self.amplitude * np.exp(-((t - center) ** 2) / (2 * self.sigma**2))

        if self.subtracted:
            waveform = waveform - waveform[-1]

        if self.axis_angle is not None:
            waveform = waveform * np.exp(1j * self.axis_angle)

        return waveform


@quam_dataclass
class FlatTopGaussianPulse(Pulse):
    """Gaussian pulse with flat top QUAM component.

    Args:
        length (int): The total length of the pulse in samples.
        amplitude (float): The amplitude of the pulse in volts.
        axis_angle (float, optional): IQ axis angle of the output pulse in radians.
            If None (default), the pulse is meant for a single channel or the I port
                of an IQ channel
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).
        flat_length (int): The length of the pulse's flat top in samples.
            The rise and fall lengths are calculated from the total length and the
            flat length.
    """

    amplitude: float
    axis_angle: float = None
    flat_length: int

    def waveform_function(self):
        from qualang_tools.config.waveform_tools import flattop_gaussian_waveform

        rise_fall_length = (self.length - self.flat_length) // 2
        if not self.flat_length + 2 * rise_fall_length == self.length:
            raise ValueError(
                "FlatTopGaussianPulse rise_fall_length (=length-flat_length) must be"
                f" a multiple of 2 ({self.length} - {self.flat_length} ="
                f" {self.length - self.flat_length})"
            )

        waveform = flattop_gaussian_waveform(
            amplitude=self.amplitude,
            flat_length=self.flat_length,
            rise_fall_length=rise_fall_length,
            return_part="all",
        )
        waveform = np.array(waveform)

        if self.axis_angle is not None:
            waveform = waveform * np.exp(1j * self.axis_angle)

        return waveform


@quam_dataclass
class FlatTopCosinePulse(Pulse):
    """Cosine rise/fall, flat-top pulse.

    Args:
        length (int): Total pulse length (samples).
        amplitude (float): Peak amplitude (V).
        flat_length (int): Flat-top length (samples). Defaults to 0 (pure cosine).
        axis_angle (float, optional): IQ axis angle in radians.
            If None (default), the pulse is meant for a single channel or the I port
                of an IQ channel.
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).
    """

    amplitude: float
    axis_angle: float = None
    flat_length: int = 0

    def waveform_function(self):
        from qualang_tools.config.waveform_tools import flattop_cosine_waveform

        rise_fall_length = (self.length - self.flat_length) // 2
        if self.flat_length + 2 * rise_fall_length != self.length:
            raise ValueError(
                "FlatTopCosinePulse requires (length - flat_length) to be even "
                f"({self.length=} {self.flat_length=})"
            )

        wf = flattop_cosine_waveform(
            amplitude=self.amplitude,
            flat_length=self.flat_length,
            rise_fall_length=rise_fall_length,
            return_part="all",
        )
        wf = np.array(wf)
        if self.axis_angle is not None:
            wf = wf * np.exp(1j * self.axis_angle)
        return wf
