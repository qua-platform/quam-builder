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


def test_waveform_amplitude_normalization():
    pulse = _make_pulse(amplitude=0.5, length=100)
    waveform = pulse.waveform_function()
    # amplitude * length mirrors SquarePulse's convention: the area under the
    # waveform equals amplitude * length, not amplitude alone.
    assert np.sum(np.abs(waveform)) == pytest.approx(0.5 * 100)


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
    expected = 0.5 * 100 * a_in / np.sum(np.abs(a_in))

    assert np.allclose(waveform, expected)


def test_sample_rate_rescales_waveform():
    waveform_1ghz = _make_pulse(sample_rate=1e9).waveform_function()
    waveform_2ghz = _make_pulse(sample_rate=2e9).waveform_function()
    assert not np.allclose(waveform_1ghz, waveform_2ghz)
