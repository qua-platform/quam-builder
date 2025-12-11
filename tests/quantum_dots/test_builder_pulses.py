"""Unit tests for quantum dot pulse generation."""

import pytest
from unittest.mock import MagicMock
from quam_builder.builder.quantum_dots.pulses import (
    add_default_ldv_qubit_pulses,
    add_default_ldv_qubit_pair_pulses,
)
from quam_builder.architecture.quantum_dots.components import XYDrive
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorSingle


class TestAddDefaultLDVQubitPulses:
    """Tests for add_default_ldv_qubit_pulses function."""

    def test_add_xy_pulses_to_qubit_with_xy_channel(self):
        """Test that XY pulses are added when qubit has xy channel."""
        # Create a mock qubit with xy channel
        qubit = MagicMock()
        qubit.xy_channel = XYDrive(opx_output="/tmp/opx", id="xy_drive")
        qubit.xy_channel.operations = {}

        # Add default pulses
        add_default_ldv_qubit_pulses(qubit)

        # Verify that all expected XY pulses were added
        expected_pulses = ["x180", "x90", "y180", "y90", "-x90", "-y90"]
        for pulse_name in expected_pulses:
            assert pulse_name in qubit.xy_channel.operations, f"Pulse {pulse_name} not found"
            assert qubit.xy_channel.operations[pulse_name] is not None

    def test_add_readout_pulses_to_qubit_with_resonator(self):
        """Test that readout pulses are added when qubit has resonator."""
        qubit = MagicMock()
        qubit.resonator = MagicMock(spec=ReadoutResonatorSingle)
        qubit.resonator.operations = {}

        # Add default pulses
        add_default_ldv_qubit_pulses(qubit)

        # Verify readout pulse was added
        assert "readout" in qubit.resonator.operations
        assert qubit.resonator.operations["readout"] is not None

    def test_add_pulses_to_qubit_with_both_xy_and_resonator(self):
        """Test adding pulses when qubit has both xy and resonator."""
        qubit = MagicMock()
        qubit.xy_channel = XYDrive(opx_output="/tmp/opx", id="xy_drive")
        qubit.xy_channel.operations = {}
        qubit.resonator = MagicMock(spec=ReadoutResonatorSingle)
        qubit.resonator.operations = {}

        add_default_ldv_qubit_pulses(qubit)

        # Verify both XY and readout pulses were added
        assert len(qubit.xy_channel.operations) == 6  # 6 XY pulses
        assert "readout" in qubit.resonator.operations

    def test_no_pulses_added_when_no_channels(self):
        """Test that no pulses are added when qubit has no xy or resonator."""
        qubit = MagicMock()
        qubit.xy_channel = None
        qubit.resonator = None

        # Should not raise an error
        add_default_ldv_qubit_pulses(qubit)

    def test_xy_pulse_properties(self):
        """Test that XY pulses have correct properties."""
        qubit = MagicMock()
        qubit.xy_channel = XYDrive(opx_output="/tmp/opx", id="xy_drive")
        qubit.xy_channel.operations = {}

        add_default_ldv_qubit_pulses(qubit)

        # Check x180 pulse properties
        x180 = qubit.xy_channel.operations["x180"]
        assert x180.length == 1000
        assert x180.amplitude == 0.2
        assert x180.axis_angle == 0.0

        # Check y90 pulse properties
        y90 = qubit.xy_channel.operations["y90"]
        assert y90.amplitude == 0.1  # Half of x180
        assert y90.axis_angle == pytest.approx(1.5707963, rel=1e-5)  # pi/2


class TestAddDefaultLDVQubitPairPulses:
    """Tests for add_default_ldv_qubit_pair_pulses function."""

    def test_qubit_pair_pulse_function_runs_without_error(self):
        """Test that the qubit pair pulse function runs (placeholder implementation)."""
        qubit_pair = MagicMock()
        qubit_pair.z = MagicMock()

        # Should not raise an error even though it's a placeholder
        add_default_ldv_qubit_pair_pulses(qubit_pair)
