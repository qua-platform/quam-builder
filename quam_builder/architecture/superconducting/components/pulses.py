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
        post_zero_padding_length (int): Extra samples included in the total length
            budget (default 0). Together with ``pulse_length``, total ``length`` is
            ``ceil((pulse_length + post_zero_padding_length) / 4) * 4``. Remaining
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
            ``pulse_length + post_zero_padding_length`` rounded up to a multiple of 4.
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
                "GaussianFilteredSymmetricBipolarPulse.post_zero_padding_length must be non-negative"
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
