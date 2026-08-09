import numpy as np
import pytest

from quam_builder.common.pulses import DrachmaReadoutPulse


def _make_pulse(**overrides):
    kwargs = dict(
        length=100,
        amplitude_integral_v_ns=0.5,
        resonator_kappa_hz=564700.0,
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
    pulse = _make_pulse(amplitude_integral_v_ns=0.5)
    waveform = pulse.waveform_function()
    assert np.sum(np.abs(waveform)) == pytest.approx(0.5)


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
