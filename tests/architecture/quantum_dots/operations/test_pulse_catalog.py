"""Tests for the pulse catalog and pulse registry."""

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
        """SingleChannel drives should produce pulse with axis_angle=None."""
        from quam.components.ports import LFFEMAnalogOutputPort
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveSingle

        xy = XYDriveSingle(
            id="test_xy",
            RF_frequency=100_000_000,
            opx_output=LFFEMAnalogOutputPort("con1", 3, port_id=1),
        )
        pulses = _make_xy_pulse_factories(xy)

        assert set(pulses.keys()) == {"gaussian"}
        pulse = pulses["gaussian"]
        assert isinstance(pulse, GaussianPulse)
        assert pulse.axis_angle is None

    def test_iq_channel_has_axis_angle(self):
        """IQ/MW channels should produce pulse with axis_angle=0.0."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        # Not a SingleChannel
        pulses = _make_xy_pulse_factories(xy)

        assert pulses["gaussian"].axis_angle == 0.0

    def test_pulse_parameters(self):
        """Verify default pulse parameters."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = _make_xy_pulse_factories(xy)

        gaussian = pulses["gaussian"]
        assert gaussian.length == 1000
        assert gaussian.amplitude == 0.2
        assert gaussian.sigma == pytest.approx(1000 / 6)


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
