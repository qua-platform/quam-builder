"""Tests for the pulse catalog and pulse registry."""

import numpy as np
import pytest

from quam.components.channels import SingleChannel
from quam.components.pulses import GaussianPulse, SquareReadoutPulse

from quam_builder.architecture.quantum_dots.operations.component_pulse_catalog import (
    _make_xy_pulse_factories,
    _make_readout_pulse,
    register_default_component_pulse_factories,
    _reset_registration,
)
from quam_builder.architecture.quantum_dots.operations.pulse_registry import (
    _reset_registry,
)


@pytest.fixture(autouse=True)
def reset_pulse_state():
    """Reset pulse registry and catalog state for each test."""
    _reset_registry()
    _reset_registration()
    yield
    _reset_registry()
    _reset_registration()


class TestMakeXYPulseFactories:
    """Test pulse factory creation for XY drives."""

    def test_single_channel_no_axis_angle(self):
        """SingleChannel drives should produce pulses with axis_angle=None."""
        from quam.components.ports import LFFEMAnalogOutputPort
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveSingle

        xy = XYDriveSingle(
            id="test_xy",
            RF_frequency=100_000_000,
            opx_output=LFFEMAnalogOutputPort("con1", 3, port_id=1),
        )
        pulses = _make_xy_pulse_factories(xy)

        assert set(pulses.keys()) == {"x180", "x90", "y180", "y90", "-x90", "-y90"}
        for name, pulse in pulses.items():
            assert isinstance(pulse, GaussianPulse), f"{name} should be GaussianPulse"
            assert pulse.axis_angle is None, f"{name} should have axis_angle=None for SingleChannel"

    def test_iq_channel_has_axis_angle(self):
        """IQ/MW channels should produce pulses with axis_angle values."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        # Not a SingleChannel
        pulses = _make_xy_pulse_factories(xy)

        assert pulses["x180"].axis_angle == 0.0
        assert pulses["y180"].axis_angle == pytest.approx(np.pi / 2)
        assert pulses["x90"].axis_angle == 0.0
        assert pulses["y90"].axis_angle == pytest.approx(np.pi / 2)

    def test_pulse_parameters(self):
        """Verify default pulse parameters."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = _make_xy_pulse_factories(xy)

        x180 = pulses["x180"]
        assert x180.length == 1000
        assert x180.amplitude == 0.2
        assert x180.sigma == pytest.approx(1000 / 6)

        x90 = pulses["x90"]
        assert x90.amplitude == 0.1  # half of 180

        neg_x90 = pulses["-x90"]
        assert neg_x90.amplitude == -0.1


class TestMakeReadoutPulse:
    """Test readout pulse factory."""

    def test_readout_pulse_type(self):
        pulse = _make_readout_pulse()
        assert isinstance(pulse, SquareReadoutPulse)

    def test_readout_pulse_parameters(self):
        pulse = _make_readout_pulse()
        assert pulse.length == 2000
        assert pulse.amplitude == 0.1


class TestRegistration:
    """Test pulse catalog registration."""

    def test_idempotent(self):
        register_default_component_pulse_factories()
        register_default_component_pulse_factories()  # should not raise

    def test_reset(self):
        register_default_component_pulse_factories()
        _reset_registration()
        # After reset, re-registration should work
        register_default_component_pulse_factories()
