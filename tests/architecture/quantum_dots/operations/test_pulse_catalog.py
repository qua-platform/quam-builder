"""Tests for the pulse builder helpers."""

import pytest

from quam.components.pulses import SquareReadoutPulse

from quam_builder.architecture.quantum_dots.components.pulses import ScalableGaussianPulse

from quam_builder.architecture.quantum_dots.operations.pulse_catalog import (
    make_xy_pulse_factories,
    make_readout_pulse,
)


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
        pulses = make_xy_pulse_factories(xy)

        assert set(pulses.keys()) == {"gaussian"}
        pulse = pulses["gaussian"]
        assert isinstance(pulse, ScalableGaussianPulse)
        assert pulse.axis_angle is None

    def test_iq_channel_has_axis_angle(self):
        """IQ/MW channels should produce pulse with axis_angle=0.0."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        # Not a SingleChannel
        pulses = make_xy_pulse_factories(xy)

        assert pulses["gaussian"].axis_angle == 0.0

    def test_pulse_parameters(self):
        """Verify default pulse parameters."""
        from unittest.mock import MagicMock
        from quam_builder.architecture.quantum_dots.components.xy_drive import XYDriveIQ

        xy = MagicMock(spec=XYDriveIQ)
        pulses = make_xy_pulse_factories(xy)

        gaussian = pulses["gaussian"]
        assert isinstance(gaussian, ScalableGaussianPulse)
        assert gaussian.length == 1000
        assert gaussian.amplitude == 1.0
        assert gaussian.sigma == pytest.approx(1000 / 6)
        assert gaussian.sigma_ratio == pytest.approx(1 / 6)


class TestMakeReadoutPulse:
    """Test readout pulse factory."""

    def test_readout_pulse_type(self):
        pulse = make_readout_pulse()
        assert isinstance(pulse, SquareReadoutPulse)

    def test_readout_pulse_parameters(self):
        pulse = make_readout_pulse()
        assert pulse.length == 2000
        assert pulse.amplitude == 1.0
