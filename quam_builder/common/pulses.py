import numpy as np

from quam.core import quam_dataclass
from quam.components.pulses import Pulse

__all__ = [
    "GaussianPulse",
    "FlatTopGaussianPulse",
    "FlatTopCosinePulse",
    "GaussianFilteredSquarePulse",
]


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


@quam_dataclass
class GaussianFilteredSquarePulse(Pulse):
    """Square core with symmetric zero pads, then 1D Gaussian filter, peak-renormalized.

    Zeros are placed left and right so the pre-filter layout is
    ``[zeros | amplitude plateau | zeros]`` over total ``length``, then
    ``gaussian_filter1d`` is applied to the **entire** array, then the real envelope
    is scaled so its peak equals ``amplitude``, then optional ``axis_angle``.

    Args:
        pulse_length (int): Samples in the constant-amplitude **core** of the
            pre-filter layout (between symmetric zero pads), not the length of a
            separately filtered segment.
        post_zero_padding_length (int): Extra samples included in the total length
            budget (default 0). Together with ``pulse_length``, total ``length`` is
            ``ceil((pulse_length + post_zero_padding_length) / 4) * 4``. Remaining
            samples relative to the core are filled with zeros split symmetrically
            left and right before filtering.
        digital_marker (str, list, optional): The digital marker to use for the pulse.
        amplitude (float): Peak amplitude in volts; after filtering, the real envelope
            is scaled by a global gain so its maximum equals this value.
        gaussian_filter_frequency_mhz (float): Frequency in MHz; filter width uses
            sigma (samples) = sample_rate / (2 * pi * f_hz) with f_hz in Hz.
        sample_rate (float): Sample rate in Hz used only for that sigma mapping
            (default 1e9). Not used for IF modulation.
        axis_angle (float, optional): IQ axis angle of the output pulse in radians.
            If None (default), the pulse is meant for a single channel or the I port
            of an IQ channel
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).
        length (int): Total waveform length in samples; inferred from
            ``pulse_length + post_zero_padding_length`` rounded up to a multiple of 4.

    Note:
        Padded regions are **not** exactly zero after filtering; the Gaussian kernel
        spreads energy from the plateau into the flanks.

        With ``f_hz = gaussian_filter_frequency_mhz * 1e6``, the Gaussian width in
        samples is ``sigma = sample_rate / (2 * pi * f_hz)``. As a rule of thumb,
        aim for each symmetric flank (roughly half of ``length - pulse_length``) to
        be at least on the order of **~5 sigma** so the smoothed waveform can decay
        toward the window edges; increase ``post_zero_padding_length`` (and thus
        inferred ``length``) if needed. Too little padding can leave significant
        amplitude at the first or last samples. This is guidance only, not enforced.
    """

    pulse_length: int
    padding_length: int = 0
    amplitude: float
    gaussian_filter_frequency_mhz: float
    sample_rate: float = 1e9
    axis_angle: float = None
    length: int = "#./inferred_length"  # pyright: ignore

    @property
    def inferred_length(self) -> int:
        return int(np.ceil((self.pulse_length + self.padding_length) / 4) * 4)

    def waveform_function(self):
        if self.pulse_length <= 0:
            raise ValueError("GaussianFilteredSquarePulse.pulse_length must be positive")
        if self.padding_length < 0:
            raise ValueError(
                "GaussianFilteredSquarePulse.post_zero_padding_length must be non-negative"
            )
        if self.gaussian_filter_frequency_mhz <= 0:
            raise ValueError(
                "GaussianFilteredSquarePulse.gaussian_filter_frequency_mhz must be positive (MHz)"
            )
        if self.sample_rate <= 0:
            raise ValueError("GaussianFilteredSquarePulse.sample_rate must be positive (Hz)")

        if self.amplitude == 0:
            return np.zeros(self.length, dtype=np.float64)

        from scipy.ndimage import gaussian_filter1d

        zero_pad_len = self.length - self.pulse_length
        left_pad = zero_pad_len // 2
        right_pad = zero_pad_len - left_pad
        env = np.concatenate(
            (
                np.zeros(left_pad, dtype=np.float64),
                self.amplitude * np.ones(self.pulse_length, dtype=np.float64),
                np.zeros(right_pad, dtype=np.float64),
            )
        )
        f_hz = self.gaussian_filter_frequency_mhz * 1e6
        sigma = self.sample_rate / (2.0 * np.pi * f_hz)
        env = gaussian_filter1d(env, sigma=sigma)
        peak = float(np.max(np.abs(env)))
        if peak > 0:
            env = env * (abs(self.amplitude) / peak)
        else:
            env = np.zeros(self.length, dtype=np.float64)

        if self.axis_angle is not None:
            env = env * np.exp(1j * self.axis_angle)
        return env
