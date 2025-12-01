"""
Comprehensive tests for create_analog_ports functionality.
Tests the various port creation functions for different instrument types.
"""
import pytest
from unittest.mock import Mock
from qualang_tools.wirer.connectivity.element import QubitReference
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from qualang_tools.wirer.instruments.instrument_channel import AnyInstrumentChannel

from quam_builder.builder.qop_connectivity.create_analog_ports import (
    create_external_mixer_reference,
    create_octave_port,
    create_mw_fem_port,
    create_lf_opx_plus_port,
    get_objects_with_same_type,
)
from quam_builder.builder.qop_connectivity.paths import (
    OCTAVES_BASE_JSON_PATH,
    PORTS_BASE_JSON_PATH,
    MIXERS_BASE_JSON_PATH,
)


class TestCreateExternalMixerReference:
    """Test the create_external_mixer_reference function."""

    def test_output_channel(self):
        """Test external mixer reference for output channel."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "output"
        channel.con = "1"

        element_id = QubitReference(0)
        line_type = WiringLineType.DRIVE

        key, reference = create_external_mixer_reference(channel, element_id, line_type)

        assert key == "frequency_converter_up"
        assert reference.startswith(MIXERS_BASE_JSON_PATH)
        assert "mixer1_q0.xy" in reference  # DRIVE.value is "xy"

    def test_input_channel(self):
        """Test external mixer reference for input channel."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "input"
        channel.con = "2"

        element_id = QubitReference(1)
        line_type = WiringLineType.RESONATOR

        key, reference = create_external_mixer_reference(channel, element_id, line_type)

        assert key == "frequency_converter_down"
        assert reference.startswith(MIXERS_BASE_JSON_PATH)
        assert "mixer2_q1.rr" in reference  # RESONATOR.value is "rr"

    def test_unknown_io_type_raises_error(self):
        """Test that unknown IO type raises ValueError."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "unknown"
        channel.con = "1"

        element_id = QubitReference(0)
        line_type = WiringLineType.DRIVE

        with pytest.raises(ValueError, match="Unknown IO type unknown"):
            create_external_mixer_reference(channel, element_id, line_type)

    def test_different_line_types(self):
        """Test external mixer reference with different line types."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "output"
        channel.con = "1"

        element_id = QubitReference(2)

        # Test FLUX line type (value is "z")
        key, reference = create_external_mixer_reference(channel, element_id, WiringLineType.FLUX)
        assert "q2.z" in reference

        # Test DRIVE line type (value is "xy")
        key, reference = create_external_mixer_reference(channel, element_id, WiringLineType.DRIVE)
        assert "q2.xy" in reference


class TestCreateOctavePort:
    """Test the create_octave_port function."""

    def test_output_port(self):
        """Test Octave port creation for output."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "output"
        channel.con = "1"
        channel.port = "1"

        key, reference = create_octave_port(channel)

        assert key == "frequency_converter_up"
        assert reference.startswith(OCTAVES_BASE_JSON_PATH)
        assert "/oct1/RF_outputs/1" in reference

    def test_input_port(self):
        """Test Octave port creation for input."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "input"
        channel.con = "2"
        channel.port = "2"

        key, reference = create_octave_port(channel)

        assert key == "frequency_converter_down"
        assert reference.startswith(OCTAVES_BASE_JSON_PATH)
        assert "/oct2/RF_inputs/2" in reference

    def test_unknown_io_type_raises_error(self):
        """Test that unknown IO type raises ValueError."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "bidirectional"
        channel.con = "1"
        channel.port = "1"

        with pytest.raises(ValueError, match="Unknown IO type bidirectional"):
            create_octave_port(channel)

    def test_different_controller_numbers(self):
        """Test Octave port with different controller numbers."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "output"
        channel.port = "3"

        # Test controller 1
        channel.con = "1"
        key, reference = create_octave_port(channel)
        assert "/oct1/" in reference

        # Test controller 5
        channel.con = "5"
        key, reference = create_octave_port(channel)
        assert "/oct5/" in reference


class TestCreateMwFemPort:
    """Test the create_mw_fem_port function."""

    def test_output_port(self):
        """Test MW-FEM port creation for output."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "output"
        channel.con = "1"
        channel.slot = "2"
        channel.port = "1"

        key, reference = create_mw_fem_port(channel)

        assert key == "opx_output"
        assert reference.startswith(PORTS_BASE_JSON_PATH)
        assert "/mw_outputs/con1/2/1" in reference

    def test_input_port(self):
        """Test MW-FEM port creation for input."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "input"
        channel.con = "1"
        channel.slot = "3"
        channel.port = "2"

        key, reference = create_mw_fem_port(channel)

        assert key == "opx_input"
        assert reference.startswith(PORTS_BASE_JSON_PATH)
        assert "/mw_inputs/con1/3/2" in reference

    def test_different_controllers_and_slots(self):
        """Test MW-FEM port with different controllers and slots."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "output"
        channel.port = "1"

        # Test controller 2, slot 4
        channel.con = "2"
        channel.slot = "4"
        key, reference = create_mw_fem_port(channel)
        assert "/con2/4/1" in reference

        # Test controller 3, slot 5
        channel.con = "3"
        channel.slot = "5"
        key, reference = create_mw_fem_port(channel)
        assert "/con3/5/1" in reference


class TestCreateLfOpxPlusPort:
    """Test the create_lf_opx_plus_port function."""

    def test_single_channel_output(self):
        """Test LF port creation with single output channel."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "output"
        channel.con = "1"
        channel.slot = "3"
        channel.port = "1"
        channel.instrument_id = "lf-fem"

        channels = [channel]

        key, reference = create_lf_opx_plus_port(channel, channels)

        assert key == "opx_output"
        assert reference.startswith(PORTS_BASE_JSON_PATH)
        assert "/analog_outputs/con1/3/1" in reference

    def test_single_channel_input(self):
        """Test LF port creation with single input channel."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "input"
        channel.con = "1"
        channel.slot = "4"
        channel.port = "2"
        channel.instrument_id = "lf-fem"

        channels = [channel]

        key, reference = create_lf_opx_plus_port(channel, channels)

        assert key == "opx_input"
        assert reference.startswith(PORTS_BASE_JSON_PATH)
        assert "/analog_inputs/con1/4/2" in reference

    def test_two_channels_iq_pair(self):
        """Test LF port creation with IQ pair (two channels)."""
        channel1 = Mock(spec=AnyInstrumentChannel)
        channel1.io_type = "output"
        channel1.con = "1"
        channel1.slot = "3"
        channel1.port = "1"
        channel1.instrument_id = "lf-fem"

        channel2 = Mock(spec=AnyInstrumentChannel)
        channel2.io_type = "output"
        channel2.con = "1"
        channel2.slot = "3"
        channel2.port = "2"
        channel2.instrument_id = "lf-fem"

        channels = [channel1, channel2]

        # First channel should be I
        key1, reference1 = create_lf_opx_plus_port(channel1, channels)
        assert key1 == "opx_output_I"
        assert "/analog_outputs/con1/3/1" in reference1

        # Second channel should be Q
        key2, reference2 = create_lf_opx_plus_port(channel2, channels)
        assert key2 == "opx_output_Q"
        assert "/analog_outputs/con1/3/2" in reference2

    def test_opx_plus_instrument(self):
        """Test OPX+ port creation (no slot in path)."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.io_type = "output"
        channel.con = "1"
        channel.port = "5"
        channel.instrument_id = "opx+"

        channels = [channel]

        key, reference = create_lf_opx_plus_port(channel, channels)

        assert key == "opx_output"
        assert reference.startswith(PORTS_BASE_JSON_PATH)
        # Should not have slot in path for OPX+
        assert "/analog_outputs/con1/5" in reference
        assert "/3/" not in reference  # No slot number

    def test_three_channels_raises_error(self):
        """Test that more than 2 channels raises NotImplementedError."""
        channel1 = Mock(spec=AnyInstrumentChannel)
        channel1.io_type = "output"
        channel1.port = "1"
        channel1.instrument_id = "lf-fem"

        channel2 = Mock(spec=AnyInstrumentChannel)
        channel2.io_type = "output"
        channel2.port = "2"
        channel2.instrument_id = "lf-fem"

        channel3 = Mock(spec=AnyInstrumentChannel)
        channel3.io_type = "output"
        channel3.port = "3"
        channel3.instrument_id = "lf-fem"

        channels = [channel1, channel2, channel3]

        with pytest.raises(NotImplementedError, match="Can't handle when channel number is not 1 or 2"):
            create_lf_opx_plus_port(channel1, channels)

    def test_iq_pair_port_assignment(self):
        """Test that I/Q assignment is based on port number order."""
        # Create channels with reversed port numbers
        channel_high = Mock(spec=AnyInstrumentChannel)
        channel_high.io_type = "output"
        channel_high.con = "1"
        channel_high.slot = "3"
        channel_high.port = "5"
        channel_high.instrument_id = "lf-fem"

        channel_low = Mock(spec=AnyInstrumentChannel)
        channel_low.io_type = "output"
        channel_low.con = "1"
        channel_low.slot = "3"
        channel_low.port = "2"
        channel_low.instrument_id = "lf-fem"

        channels = [channel_high, channel_low]

        # Lower port number should be I
        key_low, _ = create_lf_opx_plus_port(channel_low, channels)
        assert key_low == "opx_output_I"

        # Higher port number should be Q
        key_high, _ = create_lf_opx_plus_port(channel_high, channels)
        assert key_high == "opx_output_Q"


class TestGetObjectsWithSameType:
    """Test the get_objects_with_same_type utility function."""

    def test_empty_list(self):
        """Test with empty list."""
        obj = Mock()
        result = get_objects_with_same_type(obj, [])
        assert result == []

    def test_all_same_type(self):
        """Test with all objects of same type."""
        # Use actual Mock objects (not spec) since get_objects_with_same_type uses isinstance
        mock1 = Mock()
        mock2 = Mock()
        mock3 = Mock()

        lst = [mock1, mock2, mock3]
        result = get_objects_with_same_type(mock1, lst)

        # All Mock objects should match since they're the same type
        assert len(result) == 3
        assert mock1 in result
        assert mock2 in result
        assert mock3 in result

    def test_mixed_types(self):
        """Test with mixed object types."""
        mock1 = Mock()
        mock2 = Mock()
        other_obj = "not a mock"

        lst = [mock1, other_obj, mock2]
        result = get_objects_with_same_type(mock1, lst)

        # Only Mock objects should match
        assert len(result) == 2
        assert mock1 in result
        assert mock2 in result
        assert other_obj not in result

    def test_no_matching_types(self):
        """Test when no objects match the type."""
        obj = Mock()
        lst = ["string", 123, {"dict": "value"}]

        result = get_objects_with_same_type(obj, lst)
        assert result == []

    def test_single_matching_object(self):
        """Test with single matching object."""
        obj = Mock()
        matching_obj = Mock()
        different_obj = "different"

        lst = [matching_obj, different_obj]
        result = get_objects_with_same_type(obj, lst)

        # Only the Mock object should match
        assert len(result) == 1
        assert matching_obj in result

    def test_includes_self(self):
        """Test that the function includes the object itself if it's in the list."""
        obj = Mock()
        other = Mock()

        lst = [obj, other]
        result = get_objects_with_same_type(obj, lst)

        assert len(result) == 2
        assert obj in result
        assert other in result


class TestIntegrationScenarios:
    """Integration tests for realistic wiring scenarios."""

    def test_typical_qubit_wiring_scenario(self):
        """Test a typical scenario with multiple port types for a qubit."""
        # MW-FEM for drive
        drive_channel = Mock(spec=AnyInstrumentChannel)
        drive_channel.io_type = "output"
        drive_channel.con = "1"
        drive_channel.slot = "1"
        drive_channel.port = "1"
        drive_channel.instrument_id = "mw-fem"

        # LF-FEM for flux
        flux_channel = Mock(spec=AnyInstrumentChannel)
        flux_channel.io_type = "output"
        flux_channel.con = "1"
        flux_channel.slot = "3"
        flux_channel.port = "1"
        flux_channel.instrument_id = "lf-fem"

        # Octave for readout
        readout_channel = Mock(spec=AnyInstrumentChannel)
        readout_channel.io_type = "output"
        readout_channel.con = "1"
        readout_channel.port = "1"

        # Test all ports can be created
        mw_key, mw_ref = create_mw_fem_port(drive_channel)
        assert "opx_output" in mw_key
        assert "mw_outputs" in mw_ref

        lf_key, lf_ref = create_lf_opx_plus_port(flux_channel, [flux_channel])
        assert "opx_output" in lf_key
        assert "analog_outputs" in lf_ref

        octave_key, octave_ref = create_octave_port(readout_channel)
        assert "frequency_converter_up" in octave_key
        assert "RF_outputs" in octave_ref

    def test_iq_mixer_configuration(self):
        """Test IQ mixer configuration with paired channels."""
        i_channel = Mock(spec=AnyInstrumentChannel)
        i_channel.io_type = "output"
        i_channel.con = "1"
        i_channel.slot = "3"
        i_channel.port = "1"
        i_channel.instrument_id = "lf-fem"

        q_channel = Mock(spec=AnyInstrumentChannel)
        q_channel.io_type = "output"
        q_channel.con = "1"
        q_channel.slot = "3"
        q_channel.port = "2"
        q_channel.instrument_id = "lf-fem"

        channels = [i_channel, q_channel]

        i_key, i_ref = create_lf_opx_plus_port(i_channel, channels)
        q_key, q_ref = create_lf_opx_plus_port(q_channel, channels)

        # Verify I/Q assignment
        assert i_key == "opx_output_I"
        assert q_key == "opx_output_Q"

        # Verify paths are correct
        assert "/con1/3/1" in i_ref
        assert "/con1/3/2" in q_ref
