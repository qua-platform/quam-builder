import numpy as np
import pytest

from quam_builder.common.pulses import DrachmaReadoutPulse


def _make_pulse(**overrides):
    kwargs = dict(
        length=100,
        amplitude=0.5,
        kappa_ground_hz=564700.0,
        kappa_excited_hz=564700.0,
        detuning_ground_hz=299000.0,
        detuning_excited_hz=-299000.0,
    )
    kwargs.update(overrides)
    return DrachmaReadoutPulse(**kwargs)


def test_required_fields_have_no_defaults():
    with pytest.raises(TypeError):
        DrachmaReadoutPulse(length=100)


def test_waveform_shape_and_dtype():
    pulse = _make_pulse()
    waveform = pulse.waveform_function()
    assert waveform.shape == (100,)
    assert np.iscomplexobj(waveform)


def test_waveform_amplitude_is_peak():
    pulse = _make_pulse(amplitude=0.5, length=100)
    waveform = pulse.waveform_function()
    assert np.max(np.abs(waveform)) == pytest.approx(0.5)


@pytest.mark.parametrize("amplitude", [0.995, 1.0, -0.1])
def test_amplitude_out_of_bounds_raises_on_creation(amplitude):
    with pytest.raises(ValueError):
        _make_pulse(amplitude=amplitude)


@pytest.mark.parametrize("amplitude", [0.0, 0.99])
def test_amplitude_bounds_are_inclusive(amplitude):
    assert _make_pulse(amplitude=amplitude).amplitude == amplitude


def test_amplitude_changed_after_creation_is_rechecked():
    pulse = _make_pulse()
    pulse.amplitude = 1.2
    with pytest.raises(ValueError):
        pulse.waveform_function()


def test_zero_amplitude_yields_zeros():
    waveform = _make_pulse(amplitude=0.0).waveform_function()
    assert waveform.shape == (100,)
    assert np.iscomplexobj(waveform)
    assert np.all(waveform == 0)


def test_full_scale_amplitude_without_kerr_is_exact():
    waveform = _make_pulse(amplitude=0.99).waveform_function()
    assert np.max(np.abs(waveform)) == pytest.approx(0.99)


def test_full_scale_amplitude_with_kerr_drifts_slightly():
    waveform = _make_pulse(
        length=1000, amplitude=0.99, zeta_ground_hz=-175.0, zeta_excited_hz=-56.0
    ).waveform_function()
    assert np.max(np.abs(waveform)) == pytest.approx(0.99, rel=5e-3)


def test_waveform_depends_on_detuning():
    waveform_a = _make_pulse(
        detuning_ground_hz=299000.0, detuning_excited_hz=-299000.0
    ).waveform_function()
    waveform_b = _make_pulse(
        detuning_ground_hz=100000.0, detuning_excited_hz=-100000.0
    ).waveform_function()
    assert not np.allclose(waveform_a, waveform_b)


def test_zero_detuning_yields_real_waveform():
    pulse = _make_pulse(detuning_ground_hz=0.0, detuning_excited_hz=0.0)
    waveform = pulse.waveform_function()
    assert np.allclose(waveform.imag, 0, atol=1e-9)


def test_length_one_raises():
    pulse = _make_pulse(length=1)
    with pytest.raises(ValueError):
        pulse.waveform_function()


def test_zero_kappa_ground_raises():
    pulse = _make_pulse(kappa_ground_hz=0.0)
    with pytest.raises(ValueError):
        pulse.waveform_function()


def test_zero_kappa_excited_raises():
    pulse = _make_pulse(kappa_excited_hz=0.0)
    with pytest.raises(ValueError):
        pulse.waveform_function()


def test_waveform_depends_on_asymmetric_kappa():
    waveform_symmetric = _make_pulse(
        kappa_ground_hz=564700.0, kappa_excited_hz=564700.0
    ).waveform_function()
    waveform_asymmetric = _make_pulse(
        kappa_ground_hz=564700.0, kappa_excited_hz=300000.0
    ).waveform_function()
    assert not np.allclose(waveform_symmetric, waveform_asymmetric)


def test_equal_kappa_matches_legacy_shared_kappa_formula():
    """When kappa_ground_hz == kappa_excited_hz == kappa, the new per-state
    normalization sqrt(kappa_ground_hz * kappa_excited_hz) must reduce to the
    old shared-kappa formula kappa ** (n_states / 2) with n_states=2, i.e. kappa
    itself -- this is a regression check that the refactor didn't change
    behavior for the degenerate (shared-kappa) case."""
    kappa_hz = 564700.0
    pulse = _make_pulse(kappa_ground_hz=kappa_hz, kappa_excited_hz=kappa_hz)
    waveform = pulse.waveform_function()

    sample_rate = 1e9
    kappa = 2 * np.pi * kappa_hz / sample_rate
    detunings = [
        2 * np.pi * 299000.0 / sample_rate,
        2 * np.pi * -299000.0 / sample_rate,
    ]
    coeffs = np.array([1.0 + 0.0j])
    for detuning in detunings:
        factor = np.array([kappa / 2 + 1j * detuning, 1.0 + 0.0j])
        coeffs = np.convolve(coeffs, factor)

    theta = np.pi * np.arange(100) / 99
    a_T = np.sin(theta) ** 3
    derivatives = [a_T]
    current = a_T
    for _ in range(len(coeffs) - 1):
        current = np.gradient(current, 1.0)
        derivatives.append(current)

    a_in = np.zeros_like(a_T, dtype=complex)
    for k, c_k in enumerate(coeffs):
        a_in += c_k * derivatives[k]
    a_in /= kappa ** (2 / 2)
    expected = 0.5 * a_in / np.max(np.abs(a_in))

    assert np.allclose(waveform, expected)


def test_sample_rate_rescales_waveform():
    waveform_1ghz = _make_pulse(sample_rate=1e9).waveform_function()
    waveform_2ghz = _make_pulse(sample_rate=2e9).waveform_function()
    assert not np.allclose(waveform_1ghz, waveform_2ghz)


def test_zero_zeta_matches_no_kerr_waveform():
    """zeta_ground_hz=zeta_excited_hz=0.0 is the default and must reproduce the
    plain (no self-Kerr correction) waveform exactly -- self-Kerr is a strict,
    opt-in generalization."""
    waveform_default = _make_pulse().waveform_function()
    waveform_explicit_zero = _make_pulse(
        zeta_ground_hz=0.0, zeta_excited_hz=0.0
    ).waveform_function()
    assert np.allclose(waveform_default, waveform_explicit_zero)


def test_waveform_depends_on_asymmetric_zeta():
    waveform_no_kerr = _make_pulse(zeta_ground_hz=0.0, zeta_excited_hz=0.0).waveform_function()
    waveform_with_kerr = _make_pulse(
        zeta_ground_hz=-175.0, zeta_excited_hz=-56.0
    ).waveform_function()
    assert not np.allclose(waveform_no_kerr, waveform_with_kerr)


def test_waveform_shape_and_dtype_with_kerr_enabled():
    pulse = _make_pulse(zeta_ground_hz=-175.0, zeta_excited_hz=-56.0)
    waveform = pulse.waveform_function()
    assert waveform.shape == (100,)
    assert np.iscomplexobj(waveform)


def test_waveform_amplitude_is_peak_with_kerr_enabled():
    pulse = _make_pulse(amplitude=0.5, length=100, zeta_ground_hz=-175.0, zeta_excited_hz=-56.0)
    waveform = pulse.waveform_function()
    assert np.max(np.abs(waveform)) == pytest.approx(0.5, rel=1e-3)


def test_kerr_field_and_played_waveform_share_one_scale():
    """The played waveform is exactly a_in(s) for the closed-form s, with no rescale,
    so the Kerr field estimate built from s*a_T is the field that waveform drives."""
    pulse = _make_pulse(length=1000, amplitude=0.7, zeta_ground_hz=-175.0, zeta_excited_hz=-56.0)
    a_T = pulse._trial_function()
    linear_peak = np.max(np.abs(pulse._waveform_at_scale(a_T, 1.0, include_kerr=False)))
    expected = pulse._waveform_at_scale(a_T, 0.7 / linear_peak)
    assert np.allclose(pulse.waveform_function(), expected)


def test_unknown_line_gain_is_absorbed_by_zeta():
    """Scaling the drive by c and zeta by 1/c^2 leaves the Kerr shift unchanged, so
    the waveform is exactly c times the original: an unknown AWG-to-resonator gain
    only enters through zeta_phys * G^2."""
    c = 1.6
    base = _make_pulse(amplitude=0.5, zeta_ground_hz=-175.0, zeta_excited_hz=-56.0)
    scaled = _make_pulse(
        amplitude=0.5 * c, zeta_ground_hz=-175.0 / c**2, zeta_excited_hz=-56.0 / c**2
    )
    assert np.allclose(scaled.waveform_function(), c * base.waveform_function())


def test_strong_kerr_exceeding_output_range_raises():
    pulse = _make_pulse(length=2000, amplitude=0.99, zeta_ground_hz=-1000.0, zeta_excited_hz=-300.0)
    with pytest.raises(ValueError, match="zeta"):
        pulse.waveform_function()


def test_kerr_field_estimate_uses_other_state_operator():
    """In state j the resonator cancels its own factor of a_in, so the field that
    drives the Kerr shift is L_{1-j} a_T / sqrt(kappa_{1-j}); with asymmetric
    kappa/detuning this differs from the same-state pairing."""
    sample_rate = 1e9
    params = dict(
        kappa_ground_hz=564700.0,
        kappa_excited_hz=300000.0,
        detuning_ground_hz=299000.0,
        detuning_excited_hz=-100000.0,
        zeta_ground_hz=-175.0,
        zeta_excited_hz=-56.0,
    )
    pulse = _make_pulse(**params)
    a_T = pulse._trial_function()
    scale = 12.5
    detuning_ground_t, detuning_excited_t = pulse._kerr_shifted_detunings(a_T, scale)

    def per_sample(hz):
        return 2 * np.pi * hz / sample_rate

    def field(kappa_hz, detuning_hz):
        kappa = per_sample(kappa_hz)
        operator_out = (kappa / 2 + 1j * per_sample(detuning_hz)) * (scale * a_T) + np.gradient(
            scale * a_T
        )
        return operator_out / np.sqrt(kappa)

    field_ground = field(params["kappa_excited_hz"], params["detuning_excited_hz"])
    field_excited = field(params["kappa_ground_hz"], params["detuning_ground_hz"])
    expected_ground = (
        per_sample(params["detuning_ground_hz"])
        + 4 * per_sample(params["zeta_ground_hz"]) * np.abs(field_ground) ** 2
    )
    expected_excited = (
        per_sample(params["detuning_excited_hz"])
        + 4 * per_sample(params["zeta_excited_hz"]) * np.abs(field_excited) ** 2
    )

    assert np.allclose(detuning_ground_t, expected_ground)
    assert np.allclose(detuning_excited_t, expected_excited)


def test_depletion_time_ns_default_and_override():
    assert _make_pulse().depletion_time_ns == 16
    assert _make_pulse(depletion_time_ns=32).depletion_time_ns == 32
