import math
import warnings
import numpy as np

from quam.core import quam_dataclass
from quam.components.pulses import Pulse

__all__ = [
    "DragGaussianPulse",
    "DragCosinePulse",
    "DragPulse",
    "FlatTopBlackmanPulse",
    "BlackmanIntegralPulse",
    "FlatTopTanhPulse",
    "CosineBipolarPulse",
    "GaussianFilteredSymmetricBipolarPulse",
    "SNZPulse",
]


@quam_dataclass
class DragGaussianPulse(Pulse):
    """Gaussian-based DRAG pulse that compensate for the leakage and AC stark shift.

    These DRAG waveforms has been implemented following the next Refs.:
    Chen et al. PRL, 116, 020501 (2016)
    https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.116.020501
    and Chen's thesis
    https://web.physics.ucsb.edu/~martinisgroup/theses/Chen2018.pdf

    Args:
        length (int): The pulse length in ns.
        axis_angle (float, optional): IQ axis angle of the output pulse in radians.
            If None (default), the pulse is meant for a single channel or the I port
                of an IQ channel
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).
        amplitude (float): The amplitude in volts.
        sigma (float): The gaussian standard deviation.
        alpha (float): The DRAG coefficient.
        anharmonicity (float): f_21 - f_10 - The differences in energy between the 2-1
            and the 1-0 energy levels, in Hz.
        detuning (float): The frequency shift to correct for AC stark shift, in Hz.
        subtracted (bool): If true, returns a subtracted Gaussian, such that the first
            and last points will be at 0 volts. This reduces high-frequency components
            due to the initial and final points offset. Default is true.

    """

    axis_angle: float
    amplitude: float
    sigma: float
    alpha: float
    anharmonicity: float
    detuning: float = 0.0
    subtracted: bool = True

    def __post_init__(self) -> None:
        return super().__post_init__()

    def waveform_function(self):
        from qualang_tools.config.waveform_tools import drag_gaussian_pulse_waveforms

        I, Q = drag_gaussian_pulse_waveforms(
            amplitude=self.amplitude,
            length=self.length,
            sigma=self.sigma,
            alpha=self.alpha,
            anharmonicity=self.anharmonicity,
            detuning=self.detuning,
            subtracted=self.subtracted,
        )
        I, Q = np.array(I), np.array(Q)

        I_rot = I * np.cos(self.axis_angle) - Q * np.sin(self.axis_angle)
        Q_rot = I * np.sin(self.axis_angle) + Q * np.cos(self.axis_angle)

        return I_rot + 1.0j * Q_rot


@quam_dataclass
class DragPulse(DragGaussianPulse):
    def __post_init__(self) -> None:
        warnings.warn(
            "DragPulse is deprecated. Use DragGaussianPulse instead.",
            DeprecationWarning,
        )
        return super().__post_init__()


@quam_dataclass
class DragCosinePulse(Pulse):
    """Cosine based DRAG pulse that compensate for the leakage and AC stark shift.

    These DRAG waveforms has been implemented following the next Refs.:
    Chen et al. PRL, 116, 020501 (2016)
    https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.116.020501
    and Chen's thesis
    https://web.physics.ucsb.edu/~martinisgroup/theses/Chen2018.pdf

    Args:
        length (int): The pulse length in ns.
        axis_angle (float, optional): IQ axis angle of the output pulse in radians.
            If None (default), the pulse is meant for a single channel or the I port
                of an IQ channel
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).
        amplitude (float): The amplitude in volts.
        alpha (float): The DRAG coefficient.
        anharmonicity (float): f_21 - f_10 - The differences in energy between the 2-1
            and the 1-0 energy levels, in Hz.
        detuning (float): The frequency shift to correct for AC stark shift, in Hz.
    """

    axis_angle: float
    amplitude: float
    alpha: float
    anharmonicity: float
    detuning: float = 0.0

    def __post_init__(self) -> None:
        return super().__post_init__()

    def waveform_function(self):
        from qualang_tools.config.waveform_tools import drag_cosine_pulse_waveforms

        I, Q = drag_cosine_pulse_waveforms(
            amplitude=self.amplitude,
            length=self.length,
            alpha=self.alpha,
            anharmonicity=self.anharmonicity,
            detuning=self.detuning,
        )
        I, Q = np.array(I), np.array(Q)

        I_rot = I * np.cos(self.axis_angle) - Q * np.sin(self.axis_angle)
        Q_rot = I * np.sin(self.axis_angle) + Q * np.cos(self.axis_angle)

        return I_rot + 1.0j * Q_rot


@quam_dataclass
class FlatTopBlackmanPulse(Pulse):
    """Blackman rise/fall, flat-top pulse.

    Args:
        length (int): Total pulse length (samples).
        amplitude (float): Peak amplitude (V).
        flat_length (int): Flat-top length (samples).
        axis_angle (float, optional): IQ axis angle in radians.
    """

    amplitude: float
    axis_angle: float = None
    flat_length: int

    def waveform_function(self):
        from qualang_tools.config.waveform_tools import flattop_blackman_waveform

        rise_fall_length = (self.length - self.flat_length) // 2
        if self.flat_length + 2 * rise_fall_length != self.length:
            raise ValueError(
                "FlatTopBlackmanPulse requires (length - flat_length) to be even "
                f"({self.length=} {self.flat_length=})"
            )

        wf = flattop_blackman_waveform(
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
class BlackmanIntegralPulse(Pulse):
    """Adiabatic Blackman-integral ramp from v_start to v_end.

    Args:
        length (int): Pulse length (samples).
        v_start (float): Starting amplitude (V).
        v_end (float): Ending amplitude (V).
        axis_angle (float, optional): IQ axis angle in radians.
    """

    v_start: float
    v_end: float
    axis_angle: float = None

    def waveform_function(self):
        from qualang_tools.config.waveform_tools import blackman_integral_waveform

        wf = blackman_integral_waveform(
            pulse_length=self.length,
            v_start=self.v_start,
            v_end=self.v_end,
        )
        wf = np.array(wf)
        if self.axis_angle is not None:
            wf = wf * np.exp(1j * self.axis_angle)
        return wf


@quam_dataclass
class FlatTopTanhPulse(Pulse):
    """tanh rise/fall, flat-top pulse.

    Args:
        length (int): Total pulse length (samples).
        amplitude (float): Peak amplitude (V).
        flat_length (int): Flat-top length (samples). Defaults to 0.
        axis_angle (float, optional): IQ axis angle in radians.
    """

    amplitude: float
    axis_angle: float = None
    flat_length: int = 0

    def waveform_function(self):
        from qualang_tools.config.waveform_tools import flattop_tanh_waveform

        rise_fall_length = (self.length - self.flat_length) // 2
        if self.flat_length + 2 * rise_fall_length != self.length:
            raise ValueError(
                "FlatTopTanhPulse requires (length - flat_length) to be even "
                f"({self.length=} {self.flat_length=})"
            )

        wf = flattop_tanh_waveform(
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
class CosineBipolarPulse(Pulse):
    """Net-zero pulse with two symmetric cosine-shaped lobes.

    Generates a bipolar waveform with smooth cosine transitions: rise to positive
    flat, cosine switch to negative flat, then fall. The positive and negative flat
    regions are equal length so the net area is zero.

    Useful for flux pulses where DC offset must be minimised and long-timescale
    distortions avoided.

    Args:
        length (int): Total pulse length (samples).
        amplitude (float): Peak amplitude (V).
        flat_length (int): Total flat region length (samples, must be even).
            Split equally between positive and negative halves.
        axis_angle (float, optional): IQ axis angle in radians.
    """

    amplitude: float
    axis_angle: float = None
    flat_length: int

    def waveform_function(self):
        def halfcos(n: int):
            if n <= 0:
                return np.array([])
            t = np.arange(n) / n
            return 0.5 * (1 - np.cos(np.pi * t))

        def cos_switch(n: int):
            if n <= 0:
                return np.array([])
            k = np.arange(n, dtype=float)
            theta = (k + 0.5) * np.pi / n
            return np.cos(theta)

        L = int(self.length)
        F = int(self.flat_length)

        if F > L:
            raise ValueError(f"CosineBipolarPulse.flat_length={F} cannot exceed total length={L}.")
        if F % 2 != 0:
            raise ValueError(
                f"CosineBipolarPulse.flat_length={F} must be even to split equally "
                "into + and - halves."
            )

        remaining = L - F
        if remaining == 0:
            rise_len = switch_len = fall_len = 0
        else:
            base = remaining // 3
            extra = remaining % 3
            rise_len = base + (1 if extra == 2 else 0)
            switch_len = base + (extra if extra == 1 else 0)
            fall_len = base + (1 if extra == 2 else 0)

        A = float(self.amplitude)

        p = np.concatenate(
            [
                A * halfcos(rise_len),
                A * np.ones(F // 2),
                A * cos_switch(switch_len),
                -A * np.ones(F // 2),
                -A * halfcos(fall_len)[::-1],
            ]
        )

        if self.axis_angle is not None:
            p = p * np.exp(1j * self.axis_angle)

        return p.tolist()


@quam_dataclass
class GaussianFilteredSymmetricBipolarPulse(Pulse):
    """Symmetric bipolar square core with Gaussian filtering and peak renormalization.

    The pre-filter layout over total ``length`` is
    ``[zeros | +amplitude lobe | -amplitude lobe | zeros]`` where the two lobes are
    equal length and opposite sign. ``gaussian_filter1d`` is then applied to the
    entire array, the result is scaled so ``max(abs(waveform)) == amplitude``, and
    optional ``axis_angle`` is applied.

    Args:
        pulse_length (int): Total samples in the bipolar core (sum of positive and
            negative lobes). Must be positive and even.
        padding_length (int): Extra samples included in the total length
            budget (default 0). Together with ``pulse_length``, total ``length`` is
            ``ceil((pulse_length + padding_length) / 4) * 4``. Remaining
            samples are split symmetrically left/right as zeros before filtering.
        digital_marker (str, list, optional): The digital marker to use for the pulse.
        amplitude (float): Target peak magnitude in volts after filtering and
            renormalization.
        gaussian_filter_frequency_mhz (float): Frequency in MHz; filter width uses
            sigma (samples) = sample_rate / (2 * pi * f_hz) with f_hz in Hz.
        sample_rate (float): Sample rate in Hz used only for that sigma mapping
            (default 1e9). Not used for IF modulation.
        axis_angle (float, optional): IQ axis angle of the output pulse in radians.
            If None (default), the pulse is meant for a single channel or the I port
            of an IQ channel
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).
        length (int): Total waveform length in samples; inferred from
            ``pulse_length + padding_length`` rounded up to a multiple of 4.
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
            raise ValueError("GaussianFilteredSymmetricBipolarPulse.pulse_length must be positive")
        if self.pulse_length % 2 != 0:
            raise ValueError("GaussianFilteredSymmetricBipolarPulse.pulse_length must be even")
        if self.padding_length < 0:
            raise ValueError(
                "GaussianFilteredSymmetricBipolarPulse.padding_length must be non-negative"
            )
        if self.gaussian_filter_frequency_mhz <= 0:
            raise ValueError(
                "GaussianFilteredSymmetricBipolarPulse.gaussian_filter_frequency_mhz must be positive (MHz)"
            )
        if self.sample_rate <= 0:
            raise ValueError(
                "GaussianFilteredSymmetricBipolarPulse.sample_rate must be positive (Hz)"
            )

        if self.amplitude == 0:
            return np.zeros(self.length, dtype=np.float64)

        from scipy.ndimage import gaussian_filter1d

        zero_pad_len = self.length - self.pulse_length
        left_pad = zero_pad_len // 2
        right_pad = zero_pad_len - left_pad

        half_len = self.pulse_length // 2
        env = np.concatenate(
            (
                np.zeros(left_pad, dtype=np.float64),
                self.amplitude * np.ones(half_len, dtype=np.float64),
                -self.amplitude * np.ones(half_len, dtype=np.float64),
                np.zeros(right_pad, dtype=np.float64),
            )
        )

        f_hz = self.gaussian_filter_frequency_mhz * 1e6
        sigma = self.sample_rate / (2.0 * np.pi * f_hz)
        env = gaussian_filter1d(env, sigma=sigma)

        peak = float(np.max(np.abs(env)))
        if peak > 0:
            env = env * (self.amplitude / peak)
        else:
            env = np.zeros(self.length, dtype=np.float64)

        if self.axis_angle is not None:
            env = env * np.exp(1j * self.axis_angle)
        return env


@quam_dataclass
class SNZPulse(Pulse):
    """Sudden Net-Zero (SNZ) bipolar flux pulse (Di Carlo).

    Generates a bipolar waveform with abrupt transitions between the two
    lobes, separated by an idle period.  The waveform structure is::

        [padding | +A flat | +B | idle(t_phi) | -B | -A flat | padding]

    where ``t_phi_eff`` is decomposed into ``t_phi`` and ``B/A`` using the
    same mapping as the SNZ calibration scripts:

        t_phi = floor(t_phi_eff / 2) * 2
        B/A = 1 - (t_phi_eff - t_phi) / 2

    The single B / -B samples sit at the boundary between each flat section
    and the idle gap, corresponding to the last/first sampling points of the
    positive/negative lobes in the Di Carlo SNZ protocol.

    The total flat duration (both halves combined) is ``flat_length``.  Each
    half is ``flat_length // 2`` samples, so ``flat_length`` should be even.
    Args:
        amplitude (float): Peak amplitude of the flat sections (V).
        flat_length (int): Total flat-section duration in samples, split
            equally between positive and negative halves.  Should be even.
        t_phi_eff (float): Effective idle time between the two lobes in
            samples (ns at 1 GSa/s). Can be 0 for no idle gap.
        padding (int): Zero-padding added to each side of the pulse
            (samples).  Default is 0.
        axis_angle (float, optional): IQ axis angle in radians.  If None,
            the pulse targets a single channel or the I port of an IQ
            channel.
        length (int): Total waveform length in samples; auto-inferred from
            the other parameters and rounded up to a multiple of 4.
    """

    amplitude: float
    flat_length: int
    t_phi_eff: float = 0.0
    padding: int = 0
    axis_angle: float = None
    length: int = "#./inferred_length"  # pyright: ignore

    @property
    def t_phi(self) -> int:
        if self.t_phi_eff < 0:
            raise ValueError("SNZPulse.t_phi_eff must be non-negative")
        return int(math.floor(self.t_phi_eff / 2.0)) * 2

    @property
    def b_over_a_ratio(self) -> float:
        return 1.0 - (self.t_phi_eff - self.t_phi) / 2.0

    @property
    def inferred_length(self) -> int:
        raw = 2 * self.padding + self.flat_length + 2 + self.t_phi
        return int(np.ceil(raw / 4) * 4)

    def waveform_function(self):
        if self.flat_length <= 0:
            raise ValueError("SNZPulse.flat_length must be positive")
        if self.flat_length % 2 != 0:
            raise ValueError(
                f"SNZPulse.flat_length={self.flat_length} must be even to "
                "split equally into positive and negative halves."
            )
        if self.padding < 0:
            raise ValueError("SNZPulse.padding must be non-negative")

        A = float(self.amplitude)
        half = self.flat_length // 2
        B = A * self.b_over_a_ratio

        flat_pos = A * np.ones(half)
        flat_neg = -A * np.ones(half)
        idle = np.zeros(self.t_phi)

        core = np.concatenate([flat_pos, [B], idle, [-B], flat_neg])

        core_len = len(core)
        total_pad = self.length - core_len
        left_pad = total_pad // 2
        right_pad = total_pad - left_pad

        p = np.concatenate([np.zeros(left_pad), core, np.zeros(right_pad)])

        if self.axis_angle is not None:
            p = p * np.exp(1j * self.axis_angle)

        return p.tolist()


def _ceiling_with_epsilon(value: float) -> float:
    """Match quil-rs `ceiling_with_epsilon` (waveform/templates.rs).

    Subtracts a small term before ``ceil`` so values that sit just above an integer
    through floating-point drift still map down to that integer.
    """
    eps = float(np.finfo(float).eps)
    truncated = value - (value * 10.0 * eps)
    return float(np.ceil(truncated))


def _apply_phase_and_detuning_to_real_envelope(
    envelope: np.ndarray,
    phase: float,
    detuning: float,
    sample_rate: float,
) -> np.ndarray:
    """Match quil-rs `apply_phase_and_detuning_impl` for real envelopes (I only)."""
    n = np.arange(len(envelope), dtype=np.float64)
    rot = np.exp(2j * np.pi * (detuning * n / sample_rate + phase))
    return envelope.astype(np.float64, copy=False) * rot


_erf_vec = np.vectorize(math.erf, otypes=[float])


@quam_dataclass
class ErfSquarePulse(Pulse):
    """Error-function (erf) edges with a flat top, matching Quil ``ErfSquare``.

    Semantics follow `rigetti/quil-rs` ``ErfSquare`` in ``waveform/templates.rs``.

    The envelope is ``0.5 * (erf((t - t1)/sigma) - erf((t - t2)/sigma))`` with
    ``t1 = risetime/4``, ``t2 = duration - risetime/4`` (``fwhm = risetime/2``,
    ``sigma = fwhm / (4*sqrt(ln 2))``), scaled by ``amplitude``. Sample count is
    ``ceil_with_epsilon(duration * sample_rate)`` where
    ``duration = (flat_length + risetime_samples) / sample_rate``.

    ``sample_rate`` is carried on the pulse rather than read from the channel, so a
    channel that does not run at 1 GS/s must set it explicitly.

    Args:
        amplitude (float): Peak envelope scale (Quil ``scale``).
        flat_length (int): Plateau length in samples, between the two erf shoulders.
        risetime_samples (int): Quil ``risetime`` in samples at ``sample_rate``.
        sample_rate (float): Samples per second. Default 1e9.
        phase (float): Phase offset in cycles. Default 0.
        detuning (float): Frequency offset in Hz. Default 0.
        positive_polarity (bool): If False, the envelope is negated before modulation.
        post_zero_padding_length (int): Zero padding added after the pulse, in samples.
        length (int): Total sample count. Inferred from
            ``flat_length + risetime_samples + post_zero_padding_length``, rounded up to
            a multiple of 4.
    """

    amplitude: float
    flat_length: int
    risetime_samples: int
    sample_rate: float = 1e9
    phase: float = 0.0
    detuning: float = 0.0
    positive_polarity: bool = True
    post_zero_padding_length: int = 0
    length: int = "#./inferred_length"  # pyright: ignore

    @property
    def inferred_length(self) -> int:
        raw = self.flat_length + self.risetime_samples + self.post_zero_padding_length
        return int(np.ceil(raw / 4) * 4)

    def waveform_function(self):
        if self.risetime_samples <= 0:
            raise ValueError("ErfSquarePulse.risetime_samples must be positive")
        if self.flat_length < 0:
            raise ValueError("ErfSquarePulse.flat_length must be non-negative")

        duration_s = (self.flat_length + self.risetime_samples) / self.sample_rate
        risetime_s = self.risetime_samples / self.sample_rate

        n_samples = int(_ceiling_with_epsilon(duration_s * self.sample_rate))
        t = np.arange(n_samples, dtype=np.float64) / self.sample_rate

        fwhm = 0.5 * risetime_s
        t1 = fwhm
        t2 = duration_s - fwhm
        sigma = 0.5 * fwhm / (2.0 * math.log(2.0)) ** 0.5

        env = 0.5 * (_erf_vec((t - t1) / sigma) - _erf_vec((t - t2) / sigma))
        if not self.positive_polarity:
            env = -env
        env = self.amplitude * env

        zero_pad_len = self.length - len(env)
        left_pad = zero_pad_len // 2
        right_pad = zero_pad_len - left_pad
        env = np.concatenate((np.zeros(left_pad), env, np.zeros(right_pad)))

        if self.phase == 0.0 and self.detuning == 0.0:
            return env

        return _apply_phase_and_detuning_to_real_envelope(
            env, self.phase, self.detuning, self.sample_rate
        )


@quam_dataclass
class SmoothedFlatTopGaussianPulse(Pulse):
    """Flat top with Gaussian rise and fall, centered in its element.

    Unlike ``quam_builder.common.pulses.FlatTopGaussianPulse``, which derives the rise
    and fall from ``length - flat_length``, the transition time is given explicitly by
    ``smoothing_length``. Whatever is left over is zero padding, split evenly on both
    sides so the pulse stays centered -- shifting it within its element would change the
    timing of any two-qubit gate calibrated against it.

    Args:
        amplitude (float): Amplitude in volts.
        flat_length (int): Length of the flat top, in samples.
        smoothing_length (int): Total rise + fall time, in samples. Must be even.
        padding_length (int): Extra samples included in the total length. Default 0.
        sample_rate (float): Samples per second. Default 1e9.
        axis_angle (float, optional): IQ axis angle in radians. None for a single
            channel, such as a flux line.
        length (int): Total sample count. Inferred from
            ``flat_length + smoothing_length + padding_length``, rounded up to a
            multiple of 4.
    """

    amplitude: float
    flat_length: int
    smoothing_length: int = 0
    padding_length: int = 0
    sample_rate: float = 1e9
    axis_angle: float = None
    length: int = "#./inferred_length"  # pyright: ignore

    @property
    def inferred_length(self) -> int:
        raw = self.flat_length + self.smoothing_length + self.padding_length
        return int(np.ceil(raw / 4) * 4)

    def waveform_function(self):
        from qualang_tools.config.waveform_tools import flattop_gaussian_waveform

        if self.smoothing_length % 2 != 0:
            raise ValueError(
                "SmoothedFlatTopGaussianPulse.smoothing_length must be a multiple of 2"
            )

        waveform = flattop_gaussian_waveform(
            amplitude=self.amplitude,
            flat_length=self.flat_length,
            rise_fall_length=self.smoothing_length // 2,
            return_part="all",
            sampling_rate=self.sample_rate,
        )

        zero_pad_len = self.length - len(waveform)
        left_pad = zero_pad_len // 2
        right_pad = zero_pad_len - left_pad
        waveform = np.concatenate((np.zeros(left_pad), waveform, np.zeros(right_pad)))

        if self.axis_angle is not None:
            waveform = waveform * np.exp(1j * self.axis_angle)

        return waveform


@quam_dataclass
class SmoothedCosineBipolarPulse(Pulse):
    """Net-zero cosine bipolar pulse, centered in its element.

    Unlike :class:`CosineBipolarPulse`, which splits ``length - flat_length`` evenly
    into rise, switch and fall, the transition time is given explicitly by
    ``smoothing_length`` and split 1:2:1 between them. Whatever is left over is zero
    padding, split evenly on both sides so the pulse stays centered.

    The positive and negative flat regions are equal length, so the pulse integrates to
    zero.

    Args:
        amplitude (float): Peak amplitude in volts.
        flat_length (int): Total flat region length, in samples. Must be even; it is
            split equally between the positive and negative lobes.
        smoothing_length (int): Total length of the rise, switch and fall segments, in
            samples. Default 0, which gives abrupt transitions.
        padding_length (int): Extra samples included in the total length. Default 0.
        axis_angle (float, optional): IQ axis angle in radians. None for a single
            channel, such as a flux line.
        length (int): Total sample count. Inferred from
            ``flat_length + smoothing_length + padding_length``, rounded up to a
            multiple of 4.
    """

    amplitude: float
    flat_length: int
    smoothing_length: int = 0
    padding_length: int = 0
    axis_angle: float = None
    length: int = "#./inferred_length"  # pyright: ignore

    @property
    def inferred_length(self) -> int:
        raw = self.flat_length + self.smoothing_length + self.padding_length
        return int(np.ceil(raw / 4) * 4)

    def waveform_function(self):
        def halfcos(n: int):
            if n <= 0:
                return np.array([])
            t = np.arange(n) / n
            return 0.5 * (1 - np.cos(np.pi * t))

        def cos_switch(n: int):
            """Endpoint-exclusive cosine from +1 to -1 with zero discrete sum.

            Midpoint sampling keeps it antisymmetric, so the switch segment contributes
            no area and the pulse stays net-zero.
            """
            if n <= 0:
                return np.array([])
            k = np.arange(n, dtype=float)
            theta = (k + 0.5) * np.pi / n
            return np.cos(theta)

        L = int(self.length)
        F = int(self.flat_length)
        S = int(self.smoothing_length)

        if F > L:
            raise ValueError(
                f"SmoothedCosineBipolarPulse.flat_length={F} cannot exceed total length={L}."
            )
        if F % 2 != 0:
            raise ValueError(
                f"SmoothedCosineBipolarPulse.flat_length={F} must be even to split "
                "equally into + and - halves."
            )
        if L - (S + F) < 0:
            raise ValueError(
                f"SmoothedCosineBipolarPulse.smoothing_length + flat_length = {S + F} "
                f"exceeds total length={L}."
            )

        if S == 0:
            rise_len = switch_len = fall_len = 0
        else:
            base = S // 4
            extra = S % 4
            rise_len = base + (1 if extra in (2, 3) else 0)
            switch_len = 2 * base + (1 if extra in (1, 3) else 0)
            fall_len = base + (1 if extra in (2, 3) else 0)

        A = float(self.amplitude)

        zero_pad_len = L - (S + F)
        left_pad = zero_pad_len // 2
        right_pad = zero_pad_len - left_pad

        p = np.concatenate(
            [
                np.zeros(left_pad),
                A * halfcos(rise_len),
                A * np.ones(F // 2),
                A * cos_switch(switch_len),
                -A * np.ones(F // 2),
                -A * halfcos(fall_len)[::-1],
                np.zeros(right_pad),
            ]
        )

        if self.axis_angle is not None:
            p = p * np.exp(1j * self.axis_angle)

        return p.tolist()
