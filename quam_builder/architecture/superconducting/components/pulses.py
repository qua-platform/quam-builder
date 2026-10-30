import math
import warnings
from numbers import Real
from typing import Literal, Optional, Union

import numpy as np

from quam.components.pulses import Pulse
from quam.core import quam_dataclass

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
    "SmoothFlatTopPulse",
    "DragFlatTopPulse",
    "MultiderivativeCRPulse",
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
    detuning: int = 0.0
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
    detuning: int = 0.0

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
                f"FlatTopBlackmanPulse requires (length - flat_length) to be even ({self.length=} {self.flat_length=})"
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
                f"FlatTopTanhPulse requires (length - flat_length) to be even ({self.length=} {self.flat_length=})"
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
            raise ValueError(f"CosineBipolarPulse.flat_length={F} must be even to split equally into + and - halves.")

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
            raise ValueError("GaussianFilteredSymmetricBipolarPulse.padding_length must be non-negative")
        if self.gaussian_filter_frequency_mhz <= 0:
            raise ValueError(
                "GaussianFilteredSymmetricBipolarPulse.gaussian_filter_frequency_mhz must be positive (MHz)"
            )
        if self.sample_rate <= 0:
            raise ValueError("GaussianFilteredSymmetricBipolarPulse.sample_rate must be positive (Hz)")

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


@quam_dataclass
class SmoothFlatTopPulse(Pulse):
    """Shared integrated-sin^3 flat-top seed and phase/frequency modulation.

    The rising ramp matches the authors' m=3 implementation in
    pulse_shape(order="3"), not a sin^3 envelope or a raised-cosine pulse.
    With tau = rise_fall_length*1e-9 seconds and x = t/tau on the rising ramp:

        u(x) = sin(pi*x/2)^2
        s(x) = 3*u(x)^2 - 2*u(x)^3
             = 1/2 - 9*cos(pi*x)/16 + cos(3*pi*x)/16
        ds/dt = 3*pi/(4*tau) * sin(pi*t/tau)^3

    Thus s is the NORMALIZED INTEGRAL of sin^3. It rises from 0 to 1,
    remains at 1 on the plateau, and falls with the time-reversed ramp.
    Its first three derivatives vanish at both ends of each ramp; joining
    the ramps to the plateau and zero exterior gives a C^3 seed. Removing
    the plateau does not turn this m=3 seed into a raised cosine.

    Paper/source discrepancy: printed Eq. (13) uses sin^m(pi*t'/(2*t_r))
    with a ramp ending at t_r. Taken literally, its integral has nonzero
    slope at t_r, contrary to the stated boundary condition. The authors'
    m=3 source formula instead integrates sin^3(pi*t'/t_r). This class
    follows that source formula; the factor of two is an apparent error
    in the printed equation, not a change to the authors' implementation.

    Args:
        length: Inherited programmed duration in ns; an integer >= 4.
        amplitude: Seed plateau voltage in V, not pulse area or the peak
            of a derivative-corrected waveform.
        rise_fall_length: Duration of EACH rise/fall ramp in ns.
        detuning: f_drive - f_target_01 in Hz. The channel carrier
            must be f_target_01; do not also apply this frequency shift
            to the carrier. The control subclass includes it in its gaps.
        axis_angle: Constant envelope phase in radians, independently
            calibrated on the control and target channels.

    The attached channel supplies fs; QuAM defaults to 1 GS/s when
    unattached. N = length*1e-9*fs must be an integer. Samples are at n/fs,
    n=0,...,N-1; the continuous seed spans T=(N-1)/fs, with 2*tau <= T.
    Both endpoint samples are zero. Use matched sampling rates and timing
    for the control and target to share the same physical seed.

    waveform_function() returns complex samples I+1j*Q in volts:

        w(t) = envelope(t)*exp(1j*(axis_angle + 2*pi*detuning*t))
        V_RF(t) = Re[w(t)*exp(1j*omega_carrier*t)]

    Subclasses differentiate the seed BEFORE this common modulation.

    References:
        Li, Calarco & Motzoi, npj Quantum Information 10, 66 (2024),
        Eq. (13) and the m=3 construction following Eq. (29).
        DOI: 10.1038/s41534-024-00863-4.
        Author source: qiskit_utilities/cr_pulse.py, pulse_shape(order="3"):
        https://github.com/BoxiLi/qiskit-CR-calibration
    """

    amplitude: float
    rise_fall_length: float
    detuning: float = 0.0
    axis_angle: float = 0.0

    def _time(self) -> np.ndarray:
        fs = self._get_sampling_rate()
        values = [fs, self.amplitude, self.rise_fall_length, self.detuning, self.axis_angle]
        if not np.all(np.isfinite(values)) or fs <= 0:
            raise ValueError("Parameters must be finite and sample rate positive")
        if not isinstance(self.length, (int, np.integer)) or self.length < 4:
            raise ValueError("length must be an integer number of ns, >= 4")
        n_float = self.length * 1e-9 * fs
        n = round(n_float)
        if n < 4 or not np.isclose(n, n_float, rtol=0, atol=1e-8):
            raise ValueError("length must contain an integer number of samples")
        t = np.arange(n) / fs
        if not 0 < 2 * self.rise_fall_length * 1e-9 <= t[-1]:
            raise ValueError("Need 0 < 2*rise_fall_length <= length - sample_interval")
        return t

    def _seed(self, t, duration):
        """Integrated sin^3 flat top and its first three time derivatives."""
        rise = self.rise_fall_length * 1e-9
        x = np.clip(np.minimum(t, duration - t) / rise, 0, 1)
        s, c = np.sin(np.pi * x), np.cos(np.pi * x)
        u = np.sin(np.pi * x / 2) ** 2
        a, k = self.amplitude, np.pi / rise
        direction = np.where(t < duration / 2, 1.0, -1.0) * (x < 1)
        return (
            a * u * u * (3 - 2 * u),
            a * 3 * k / 4 * s**3 * direction,
            a * 9 * k * k / 4 * s * s * c * (x < 1),
            a * 9 * k**3 / 4 * s * (2 * c * c - s * s) * direction,
        )

    def _envelope(self, t) -> np.ndarray:
        return self._seed(t, t[-1])[0].astype(complex)

    def waveform_function(self) -> np.ndarray:
        t = self._time()
        # Differentiate the unmodulated seed, not its carrier phase ramp.
        phase = self.axis_angle + 2 * np.pi * self.detuning * t
        return self._envelope(t) * np.exp(1j * phase)


@quam_dataclass
class DragFlatTopPulse(SmoothFlatTopPulse):
    """Target cancellation with a dimensionless, calibrated DRAG alpha.

    Uses the shared integrated-sin^3 seed v(t), NOT the control's final
    multiderivative waveform. Before inherited phase/frequency modulation:

        D_target = 2*pi*(anharmonicity - detuning)  # rad/s
        c_iy = alpha/D_target                           # seconds
        w_target = v + 1j*c_iy*dv/dt                     # volts

    Args:
        anharmonicity: TARGET f12 - f01, in Hz. Same typical definition as
            qualang_tools.config.waveform_tools.drag_gaussian_pulse_waveforms
            / drag_cosine_pulse_waveforms (there spelled f_21 - f_10, the same
            quantity). Physically always negative for a transmon; only the
            magnitude of the stored value is used and the sign is fixed
            internally, guarding against calibration data that stores the
            magnitude as positive.
        alpha: Signed, dimensionless derivative strength, default 0 (off).
            Uses the same coefficient convention as the Gaussian/cosine
            DRAG helpers. It is NOT a time in seconds or nanoseconds.
        Inherited parameters retain SmoothFlatTopPulse's definitions.

    The denominator only PARAMETERIZES the empirical coefficient c_iy;
    it does not predict the coefficient that cancels ZZ. A target alpha
    optimized for single-qubit leakage is not automatically suitable here.
    There is no target Givens mode: this is always first-derivative IY
    shaping, independently calibrated even when the CONTROL uses Givens.
    Nonzero alpha requires a nonzero D_target. alpha=0 returns the seed.

    Migration from the old time-valued coefficient:

        alpha = 2*pi*(anharmonicity - detuning)*c_iy
        alpha = 2*pi*(anharmonicity - detuning)*c_iy_ns*1e-9

    The old c_iy/c_iy_ns constructor arguments are replaced, not aliased.
    Changing detuning with fixed alpha changes c_iy as well; use the
    conversion above to preserve a time-valued coefficient during a sweep.

    Match the control's length, rise_fall_length, detuning and sample rate,
    and play synchronously. Target amplitude and axis_angle are independent
    calibrations. Differentiate BEFORE applying frequency modulation so no
    unintended plateau term is introduced. At axis_angle=detuning=0,
    Q vanishes on the plateau; amplitude=0 removes both quadratures.

    Calibrate target amplitude/phase with alpha=0, then sweep alpha and
    locate the residual-ZZ zero crossing by Hamiltonian tomography. This
    is an approximate derivative ansatz, not exact instantaneous removal
    of IX/IY/ZZ, and includes no separate leakage or line-response model.

    References:
        Li, Calarco & Motzoi, npj Quantum Information 10, 66 (2024),
        "Application to multi-qubit operator errors", Fig. 3.
        DOI: 10.1038/s41534-024-00863-4.
        Coefficient convention: qualang_tools.config.waveform_tools,
        drag_gaussian_pulse_waveforms / drag_cosine_pulse_waveforms.
        See SmoothFlatTopPulse for the seed and Eq. (13) discrepancy.
    """

    anharmonicity: float
    alpha: float = 0.0

    def _envelope(self, t) -> np.ndarray:
        if not np.all(np.isfinite([self.alpha, self.anharmonicity])):
            raise ValueError("alpha and target anharmonicity must be finite")
        v, dv, *_ = self._seed(t, t[-1])
        if self.alpha == 0:
            return v.astype(complex)
        # A transmon's anharmonicity (f12 - f01) is always negative; only the
        # magnitude of the stored value is physically meaningful, so the sign
        # is fixed here rather than trusted from the input. See the typical
        # definition in
        # qualang_tools.config.waveform_tools.drag_gaussian_pulse_waveforms.
        anharmonicity = -abs(self.anharmonicity)
        delta = 2 * np.pi * (anharmonicity - self.detuning)
        if delta == 0:
            raise ValueError("Nonzero alpha requires anharmonicity != detuning")
        return v + 1j * (self.alpha / delta) * dv


@quam_dataclass
class MultiderivativeCRPulse(SmoothFlatTopPulse):
    """Control-qubit CR pulse with recursive multi-derivative corrections.

    Drives the CONTROL near the TARGET frequency; this is distinct from
    the target correction in DragFlatTopPulse. The uncorrected seed is
    the authors' m=3 integrated-sin^3 flat top. See SmoothFlatTopPulse for
    its formula, endpoint convention and the printed Eq. (13) discrepancy.

    Args:
        qubit_detuning: f_control_01 - f_target_01 in Hz, signed.
        anharmonicity: f_control_12 - f_control_01 in Hz. This is the same
            typical definition used throughout this module and by
            qualang_tools.config.waveform_tools.drag_gaussian_pulse_waveforms /
            drag_cosine_pulse_waveforms (there spelled f_21 - f_10, the same
            quantity). A transmon's 1-2 transition always sits below its 0-1
            transition, so this is physically always negative; only its
            magnitude is taken from the stored value and the sign is fixed
            internally to match that physical convention, guarding against
            calibration data that stores the magnitude as positive.
        method: "perturbative" or "givens" for the single-photon steps.
        alphas: Three signed dimensionless multipliers (a01, a12, a02),
            default (1, 1, 1). Adjustable ONLY for method="perturbative".
            Zero disables the corresponding correction; unity retains its
            analytical value. This is not overall amplitude scaling.
            Givens requires (1, 1, 1); non-unity values raise ValueError
            rather than silently changing or ignoring the correction.
        pi_area: Positive reference area in V*s, or the CONTROL qubit's
            calibrated resonant pi Pulse. Required only for "givens".
            All inherited pulse parameters retain SmoothFlatTopPulse's
            definitions; amplitude is a seed voltage, not a rotation angle.

    The signed angular-frequency gaps include detuning:

        D10 = 2*pi*(qubit_detuning - detuning)
        D21 = D10 + 2*pi*anharmonicity
        D20 = D10 + D21

    Starting from the real seed v, apply the two-photon step first:

        z2^2 = v^2 - (1j*a02/D20)*d(v^2)/dt

    The continuous square-root branch preserves the seed amplitude sign.
    Next apply the 01 step, then the 12 step. Their shared operator is:

        F_P[z] = z - 1j*a_jk*dz/dt / D
        F_G[z] = z - (1j/D)*(dz/dt
                 - z*Re(conj(z)*dz/dt)/(|z|^2 + (D/g)^2))

    For Givens, all scales are fixed to one, g01=pi/A_pi and
    g12=sqrt(2)*g01, in rad/s/V. The two-photon step remains perturbative
    for BOTH methods. A Givens step is exact only for its isolated two-level
    subsystem, not the full coupled system. Zero gaps remain rejected even
    when a corresponding scale is zero; nonzero gaps alone do not establish
    validity near resonance. The result is conjugated into the I+1j*Q convention
    before the inherited constant phase and frequency modulation.

    Reference-area evaluation:
        A numeric pi_area is used directly. A Pulse is evaluated through
        calculate_waveform(). Constant waveforms use abs(V)*length*1e-9;
        sampled waveforms use abs(sum(V))/fs at the REFERENCE sample rate,
        not sum(abs(V))/fs or the CR channel's rate. Known positive phase
        ramps are removed using detuning, or detuning if detuning
        is absent. A constant axis rotation does not change this area.

        This assumes a resonant, approximately fixed-axis pi calibration;
        ordinary DRAG with zero net derivative-quadrature area is allowed.
        It is a pulse-area estimate, not an exact gain extraction for
        arbitrary composite, chirped or noncommuting multilevel dynamics.
        Runtime amplitude scaling must be included in the calibration.
        The voltage-to-Rabi gain is assumed unchanged at the CR frequency;
        a frequency-dependent line response needs a separate correction.
        For other reference conventions, supply a numeric pi_area.

        An already-owned Pulse is stored as a live QuAM reference without
        reparenting it. Both pulses must belong to the same QuamRoot.
        Unattached reference pulses default to QuAM's 1 GS/s sample rate.
        The area is recomputed on waveform generation, not cached.

    All derivatives are analytic; there is no oversampling or final
    normalization. Regenerate after changing amplitude or duration:
    scaling a generated Givens waveform with QUA amp(...) or stretching
    it does not recompute the nonlinear corrections. This class neither
    calibrates the ZX gate angle nor supplies the separate target pulse.

    Reference:
        Li, Calarco & Motzoi, npj Quantum Information 10, 66 (2024),
        Eqs. (4), (7)-(12) and Supplementary Note 5 (tunable coefficients).
        See SmoothFlatTopPulse for the seed source. Fixing all Givens scales
        to unity is an interface restriction here, not a claim that the
        authors prohibit tuning them.
        DOI: 10.1038/s41534-024-00863-4.
    """

    qubit_detuning: float
    anharmonicity: float
    method: Literal["perturbative", "givens"] = "perturbative"
    alphas: tuple[float, float, float] = (1.0, 1.0, 1.0)
    pi_area: Optional[Union[float, Pulse]] = None

    def __setattr__(self, name, value):
        if name == "pi_area" and isinstance(value, Pulse):
            if value is self:
                raise ValueError("pi_area cannot refer to the CR pulse itself")
            # A calibration pulse already belongs to its control channel.
            # Store a live reference rather than trying to reparent it.
            if value.parent is not None:
                value = value.get_reference()
        super().__setattr__(name, value)

    def _get_pi_area(self) -> float:
        reference = self.pi_area  # QuAM resolves string references here.
        area = reference
        if isinstance(reference, Pulse):
            if reference is self:
                raise ValueError("pi_area cannot refer to the CR pulse itself")
            waveform = reference.calculate_waveform()
            if waveform is None:
                raise ValueError("The reference pi pulse has no analog waveform")
            w = np.asarray(waveform, dtype=complex)
            if w.ndim > 1 or w.size == 0 or not np.all(np.isfinite(w)):
                raise ValueError("The reference waveform must be finite and scalar or 1D")
            if w.ndim == 0:
                area = abs(w.item()) * reference.length * 1e-9
            else:
                fs = reference._get_sampling_rate()
                # These attributes use the same positive phase-ramp convention.
                freq = getattr(reference, "detuning", getattr(reference, "detuning", 0.0))
                if not np.all(np.isfinite([fs, freq])) or fs <= 0:
                    raise ValueError("Invalid reference sample rate or detuning")
                w = w * np.exp(-2j * np.pi * freq * np.arange(w.size) / fs)
                area = abs(np.sum(w)) / fs
        if isinstance(area, bool) or not isinstance(area, Real):
            raise ValueError("pi_area must be a positive number or a resolved pi Pulse")
        if not np.isfinite(area) or area <= 0:
            raise ValueError("The reference pi area must be finite and positive, in V*s")
        return float(area)

    @property
    def alpha(self) -> float:
        # convential alpha definition refers to a_10
        return self.alphas[0]

    @alpha.setter
    def alpha(self, value: float):
        self.alphas = (value, self.alphas[1], self.alphas[2])

    @staticmethod
    def _drag(z, dz, delta, gain=None, ddz=None, scale=1.0):
        """Single-photon step, optionally with its analytic derivative.

        gain=None: perturbative with scale; Givens uses scale=1.
        """
        if scale == 0:
            return z if ddz is None else (z, dz)
        slope, curvature = dz, ddz
        if gain is not None:
            den = np.abs(z) ** 2 + (delta / gain) ** 2
            projection = np.real(z.conj() * dz) / den
            slope = dz - z * projection
            if ddz is not None:
                dp = (np.abs(dz) ** 2 + np.real(z.conj() * ddz) - 2 * projection * np.real(z.conj() * dz)) / den
                curvature = ddz - dz * projection - z * dp
        out = z - 1j * slope / delta * scale
        return out if ddz is None else (out, dz - 1j * curvature / delta * scale)

    def _envelope(self, t) -> np.ndarray:
        if not np.all(np.isfinite([self.qubit_detuning, self.anharmonicity])):
            raise ValueError("qubit_detuning and anharmonicity must be finite")
        if self.method not in ("perturbative", "givens"):
            raise ValueError("method must be 'perturbative' or 'givens'")
        try:
            scales = tuple(self.alphas)
        except TypeError as exc:
            raise ValueError("alphas must contain three finite real numbers") from exc
        if len(scales) != 3 or any(
            isinstance(s, bool) or not isinstance(s, Real) or not np.isfinite(s) for s in scales
        ):
            raise ValueError("alphas must contain three finite real numbers")
        if self.method == "givens" and scales != (1.0, 1.0, 1.0):
            raise ValueError("Givens requires alphas=(1, 1, 1)")
        a01, a12, a02 = scales
        # A transmon's anharmonicity (f_control_12 - f_control_01) is always
        # negative; only the magnitude of the stored value is physically
        # meaningful, so the sign is fixed here rather than trusted from the
        # input. See the typical definition in
        # qualang_tools.config.waveform_tools.drag_gaussian_pulse_waveforms.
        anharmonicity = -abs(self.anharmonicity)
        d10 = 2 * np.pi * (self.qubit_detuning - self.detuning)
        d21 = d10 + 2 * np.pi * anharmonicity
        d20 = d10 + d21
        if min(abs(d10), abs(d21), abs(d20)) == 0:
            raise ValueError("A transition is resonant; the recursion is singular")
        gain = np.pi / self._get_pi_area() if self.method == "givens" else None

        v, dv, ddv, dddv = self._seed(t, t[-1])
        if a02 == 0:
            z, dz, ddz = v.astype(complex), dv.astype(complex), ddv.astype(complex)
        else:
            r = v * v - 2j * v * dv / d20 * a02
            dr = 2 * v * dv - 2j * (dv * dv + v * ddv) / d20 * a02
            ddr = 2 * (dv * dv + v * ddv) - 2j * (3 * dv * ddv + v * dddv) / d20 * a02
            # Re(r) >= 0: principal root is continuous; preserve amplitude sign.
            z = np.sign(self.amplitude) * np.sqrt(r)
            dz = np.divide(dr, 2 * z, out=np.zeros_like(z), where=(z != 0))
            ddz = np.divide(ddr - 2 * dz * dz, 2 * z, out=np.zeros_like(z), where=(z != 0))
        z, dz = self._drag(z, dz, d10, gain, ddz, scale=a01)
        z = self._drag(z, dz, d21, None if gain is None else np.sqrt(2) * gain, scale=a12)
        return z.conj()  # Paper's raising-operator convention -> I+1j*Q.
