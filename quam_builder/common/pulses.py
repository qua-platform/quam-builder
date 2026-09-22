import numpy as np
from quam.core import quam_dataclass
from quam.components.pulses import Pulse, ReadoutPulse

__all__ = [
    "GaussianPulse",
    "FlatTopGaussianPulse",
    "FlatTopCosinePulse",
    "GaussianFilteredSquarePulse",
    "DrachmaReadoutPulse",
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


@quam_dataclass
class DrachmaReadoutPulse(ReadoutPulse):
    """DRACHMA readout scheme, as described in Jerger et al.,
    "Dispersive Qubit Readout with Intrinsic Resonator Reset" (arXiv:2406.04891).

    The pulse is built from the analytic trial function a_T(t) = sin^3(pi t / Tp)
    and inverted through the state-dependent resonator response, following
    Eqs. (6)-(7) of the paper:

        a_in(t) = [ prod_j (kappa/2 + i*chi_j + d/dt) ] a_T(t) / kappa^(N/2)

    where chi_j are the dispersive shifts of each computational state relative
    to the drive carrier and kappa is the resonator linewidth. For N=2 states
    this is just a second-order differential operator acting on a_T(t), so we
    apply it directly in the time domain -- no FFT/deconvolution required.

    IMPORTANT: detuning_ground_hz / detuning_excited_hz are defined relative
    to the drive carrier, which the paper places halfway between the
    ground- and excited-state resonator frequencies (detuning_{0,1} = +-chi
    in the paper's notation, where chi is the dispersive shift).

    NOTE: the paper itself uses a single shared kappa for all states in Eq. (7)
    above -- there is no per-state kappa_j anywhere in Jerger et al. The split
    into kappa_ground_hz / kappa_excited_hz below is OUR OWN extension, not a
    result from the paper. It is motivated by the generic input-output equation
    for a driven-dissipative resonator conditioned on state j,
    da_j/dt = -(kappa_j/2 + i*chi_j)*a_j + sqrt(kappa_j)*a_in(t), which gives
    each factor in the product its own kappa_j when the resonator linewidth is
    state-dependent in practice (e.g. state-dependent Purcell decay or extra
    loss channels when the qubit is excited). We generalize the normalization
    from kappa^(N/2) in Eq. (7) to sqrt(kappa_ground_hz * kappa_excited_hz),
    which reduces to the original formula when kappa_ground_hz == kappa_excited_hz.
    This extension has not been validated against the paper or experimentally;
    treat it as a heuristic, not a derived result.

    SELF-KERR (zeta_ground_hz / zeta_excited_hz, optional, default 0): the paper's
    Section II.4 documents a real state-dependent effect -- self-Kerr -- where the
    dispersive shift becomes amplitude-dependent: chi_j -> chi_j + 4*zeta_j*|a_j(t)|^2
    (their Eq. 8), with measured zeta_0/2pi = -175 Hz, zeta_1/2pi = -56 Hz in their
    device. We implement their single-pass (non-iterative) correction, Eqs. (9)-(10),
    generalized with our per-state kappa_j:

        a_j~(t) = [kappa_j/2 + i*chi_j + d/dt] a_T(t) / sqrt(kappa_j)     (Eq. 9)
        a_in(t) = [prod_j (kappa_j/2 + i*(chi_j + 4*zeta_j*|a_j~(t)|^2) + d/dt)]
                  a_T(t) / sqrt(kappa_ground_hz * kappa_excited_hz)        (Eq. 10)

    Because this codebase has no absolute photon-number calibration (amplitude is
    an AWG-voltage convention, not physical photon number -- see the amplitude field
    below), the amplitude-scaled trial function amplitude*a_T(t) is used as the
    stand-in field for a_j~(t) in Eq. 9. This makes zeta_*_hz an empirical per-setup
    tuning knob rather than a first-principles rate. Leaving zeta_ground_hz and
    zeta_excited_hz at their default of 0 exactly recovers the no-Kerr waveform.

    kappa_*_hz, detuning_*_hz, and zeta_*_hz are given in Hz and converted internally
    (via a factor of 1/sample_rate) to the per-sample units used by kappa/2pi,
    chi/2pi, zeta/2pi in the paper (e.g. for sample_rate = 1e9 Sa/s, kappa/2pi =
    0.5647 MHz -> kappa_ground_hz = 564700).

    Args:
        sample_rate (float): Sample rate in Hz used to convert kappa_*_hz,
            detuning_*_hz, and zeta_*_hz to per-sample units (default 1e9, i.e. 1
            sample = 1 ns).
    """

    amplitude: float  # NOT a peak amplitude, determines the area under the graph similar to square pulse amplitude
    kappa_ground_hz: float  # kappa_g/(2*pi), resonator linewidth for |g>, Hz
    kappa_excited_hz: float  # kappa_e/(2*pi), resonator linewidth for |e>, Hz
    detuning_ground_hz: float  # detuning of ground state relative to carrier, Hz
    detuning_excited_hz: float  # detuning of excited state relative to carrier, Hz
    zeta_ground_hz: float = 0.0  # ground-state self-Kerr coeff, zeta_0/(2*pi), Hz
    zeta_excited_hz: float = 0.0  # excited-state self-Kerr coeff, zeta_1/(2*pi), Hz
    depletion_time_ns: int = (
        16  # extra time after the pulse to wait for the resonator to decay before measurement
    )
    sample_rate: float = 1e9

    def _trial_function(self):
        """sin^3(pi t / Tp), sampled so BOTH endpoints are exactly zero.
        (Needed because the smoothness condition requires a_T and its first
        N-1 derivatives to vanish at t=0 and t=Tp; np.arange(length)/length
        never actually reaches the second boundary.)"""
        theta = np.pi * np.arange(self.length) / (self.length - 1)
        return np.sin(theta) ** 3

    @staticmethod
    def _apply_first_order_operator(signal, kappa, detuning, dt=1.0):
        """Apply (kappa/2 + i*detuning + d/dt) to signal via a centered finite
        difference for d/dt. detuning may be a scalar (constant chi_j) or a
        per-sample array (Kerr-corrected, time-varying chi_j(t))."""
        return (kappa / 2 + 1j * detuning) * signal + np.gradient(signal, dt)

    def _kerr_shifted_detunings(self, a_T):
        """Eq. (9) generalized with per-state kappa_j: a one-shot (non-iterative)
        estimate of each state's intracavity field, used only to evaluate the
        self-Kerr correction chi_j -> chi_j + 4*zeta_j*|a_j~(t)|^2 (Eq. 10). No-op
        (returns the plain constant detunings) when zeta_ground_hz and
        zeta_excited_hz are both 0."""
        a_T_scaled = self.amplitude * a_T
        corrected_detunings = []
        for kappa_hz, detuning_hz, zeta_hz in (
            (self.kappa_ground_hz, self.detuning_ground_hz, self.zeta_ground_hz),
            (self.kappa_excited_hz, self.detuning_excited_hz, self.zeta_excited_hz),
        ):
            kappa = 2 * np.pi * kappa_hz / self.sample_rate
            detuning = 2 * np.pi * detuning_hz / self.sample_rate
            a_tilde = self._apply_first_order_operator(a_T_scaled, kappa, detuning)
            a_tilde = a_tilde / np.sqrt(kappa)
            zeta = 2 * np.pi * zeta_hz / self.sample_rate
            corrected_detunings.append(detuning + 4 * zeta * np.abs(a_tilde) ** 2)
        return corrected_detunings

    def waveform_function(self):
        """Constructs a_in(t) per Eq. (7)/Eq. (10), applying the state factors
        as first-order differential operators sequentially on a_T(t) =
        sin^3(pi t / Tp). Sequential (rather than expanding the product into a
        constant-coefficient polynomial in D) is required because the
        self-Kerr-corrected chi_j(t) (see _kerr_shifted_detunings) is a
        per-sample array, not a scalar, when zeta_ground_hz/zeta_excited_hz are
        nonzero; with zeta=0 this reduces exactly to the plain Eq. (7) waveform.

        prod_{j=0}^{1} acting on a_T means operator_0 . operator_1, so the
        excited-state (j=1) factor is applied first, then the ground-state
        (j=0) factor is applied to that result.
        """
        if self.length < 2:
            raise ValueError(
                "DrachmaReadoutPulse.length must be at least 2 samples "
                f"(got {self.length}); the trial function is undefined for length == 1."
            )
        if self.kappa_ground_hz <= 0:
            raise ValueError(
                "DrachmaReadoutPulse.kappa_ground_hz must be positive "
                f"(got {self.kappa_ground_hz})"
            )
        if self.kappa_excited_hz <= 0:
            raise ValueError(
                "DrachmaReadoutPulse.kappa_excited_hz must be positive "
                f"(got {self.kappa_excited_hz})"
            )
        if self.sample_rate <= 0:
            raise ValueError(
                f"DrachmaReadoutPulse.sample_rate must be positive (got {self.sample_rate})"
            )

        norm = self.amplitude * self.length
        kappa_ground = 2 * np.pi * self.kappa_ground_hz / self.sample_rate
        kappa_excited = 2 * np.pi * self.kappa_excited_hz / self.sample_rate
        kappa_norm = np.sqrt(kappa_ground * kappa_excited)
        a_T = self._trial_function()

        detuning_ground_t, detuning_excited_t = self._kerr_shifted_detunings(a_T)

        a_in = self._apply_first_order_operator(a_T, kappa_excited, detuning_excited_t)
        a_in = self._apply_first_order_operator(a_in, kappa_ground, detuning_ground_t)
        a_in = a_in / kappa_norm

        a_in_sum = np.sum(np.abs(a_in))
        if a_in_sum == 0:
            raise ValueError(
                "DrachmaReadoutPulse waveform_function produced an all-zero waveform "
                "before normalization; cannot normalize to the requested amplitude."
            )
        a_in = norm * a_in / a_in_sum  # normalize to desired amplitude

        return a_in
