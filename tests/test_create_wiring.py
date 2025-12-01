"""
Comprehensive tests for create_wiring functionality.
These tests capture the current behavior to ensure refactoring doesn't break functionality.
"""
import pytest
from unittest.mock import Mock, MagicMock
from typing import List
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from qualang_tools.wirer.connectivity.element import QubitReference, QubitPairReference, ElementReference
from qualang_tools.wirer.instruments.instrument_channel import AnyInstrumentChannel
from qualang_tools.wirer import Connectivity

from quam_builder.builder.qop_connectivity.create_wiring import (
    create_wiring,
    qubit_wiring,
    qubit_pair_wiring,
    global_element_wiring,
    readout_wiring,
    get_channel_port,
    set_nested_value_with_path,
)


class TestSetNestedValueWithPath:
    """Test the set_nested_value_with_path utility function."""

    def test_simple_path(self):
        """Test setting a value with a simple path."""
        d = {}
        set_nested_value_with_path(d, "key1/key2", "value")
        assert d == {"key1": {"key2": "value"}}

    def test_deep_nesting(self):
        """Test setting a value with deep nesting."""
        d = {}
        set_nested_value_with_path(d, "a/b/c/d/e", "deep_value")
        assert d == {"a": {"b": {"c": {"d": {"e": "deep_value"}}}}}

    def test_overwrite_existing(self):
        """Test that existing values are overwritten."""
        d = {"key1": {"key2": "old_value"}}
        set_nested_value_with_path(d, "key1/key2", "new_value")
        assert d == {"key1": {"key2": "new_value"}}

    def test_add_sibling_keys(self):
        """Test adding sibling keys at the same level."""
        d = {}
        set_nested_value_with_path(d, "parent/child1", "value1")
        set_nested_value_with_path(d, "parent/child2", "value2")
        assert d == {"parent": {"child1": "value1", "child2": "value2"}}


class TestGetChannelPort:
    """Test the get_channel_port function."""

    def test_digital_channel(self):
        """Test handling of digital channels."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "digital"
        channel.io_type = "output"

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_digital_output_port') as mock_create:
            mock_create.return_value = ("digital_key", "digital_ref")
            key, reference = get_channel_port(channel, [channel])

        assert key == "digital_key"
        assert reference == "digital_ref"
        mock_create.assert_called_once_with(channel)

    def test_octave_channel(self):
        """Test handling of Octave channels."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "octave"

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_octave_port') as mock_create:
            mock_create.return_value = ("octave_key", "octave_ref")
            key, reference = get_channel_port(channel, [channel])

        assert key == "octave_key"
        assert reference == "octave_ref"
        mock_create.assert_called_once_with(channel)

    def test_mw_fem_channel(self):
        """Test handling of MW-FEM channels."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "mw-fem"

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_mw_fem_port') as mock_create:
            mock_create.return_value = ("mw_fem_key", "mw_fem_ref")
            key, reference = get_channel_port(channel, [channel])

        assert key == "mw_fem_key"
        assert reference == "mw_fem_ref"
        mock_create.assert_called_once_with(channel)

    def test_lf_fem_channel(self):
        """Test handling of LF-FEM channels."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "lf-fem"
        channels = [channel]

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_lf_opx_plus_port') as mock_create:
            mock_create.return_value = ("lf_fem_key", "lf_fem_ref")
            key, reference = get_channel_port(channel, channels)

        assert key == "lf_fem_key"
        assert reference == "lf_fem_ref"
        mock_create.assert_called_once_with(channel, channels)

    def test_opx_plus_channel(self):
        """Test handling of OPX+ channels."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "opx+"
        channels = [channel]

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_lf_opx_plus_port') as mock_create:
            mock_create.return_value = ("opx_key", "opx_ref")
            key, reference = get_channel_port(channel, channels)

        assert key == "opx_key"
        assert reference == "opx_ref"
        mock_create.assert_called_once_with(channel, channels)

    def test_unknown_instrument_raises_error(self):
        """Test that unknown instrument types raise ValueError."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "unknown-instrument"

        with pytest.raises(ValueError, match="Unknown instrument type unknown-instrument"):
            get_channel_port(channel, [channel])


class TestQubitWiring:
    """Test the qubit_wiring function."""

    def test_basic_analog_channel(self):
        """Test basic wiring with analog channel."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "octave"
        channel.io_type = "output"

        element_id = QubitReference(0)
        line_type = WiringLineType.DRIVE

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_octave_port') as mock_create:
            mock_create.return_value = ("opx_output", "#/ports/port1")
            result = qubit_wiring([channel], element_id, line_type)

        assert "opx_output" in result
        assert result["opx_output"] == "#/ports/port1"

    def test_external_mixer_channel(self):
        """Test handling of external mixer channels."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "external-mixer"
        channel.io_type = "output"
        channel.con = "con1"

        element_id = QubitReference(0)
        line_type = WiringLineType.DRIVE

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_external_mixer_reference') as mock_create:
            mock_create.return_value = ("frequency_converter_up", "#/mixers/mixer_ref")
            result = qubit_wiring([channel], element_id, line_type)

        assert "frequency_converter_up" in result
        assert result["frequency_converter_up"] == "#/mixers/mixer_ref"

    def test_filters_digital_inputs(self):
        """Test that digital input channels are filtered out."""
        analog_channel = Mock(spec=AnyInstrumentChannel)
        analog_channel.signal_type = "analog"
        analog_channel.instrument_id = "octave"

        digital_input = Mock(spec=AnyInstrumentChannel)
        digital_input.signal_type = "digital"
        digital_input.io_type = "input"

        element_id = QubitReference(0)
        line_type = WiringLineType.DRIVE

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_octave_port') as mock_create:
            mock_create.return_value = ("opx_output", "#/ports/port1")
            result = qubit_wiring([analog_channel, digital_input], element_id, line_type)

        # Should only have one entry (the analog channel)
        assert len(result) == 1
        assert "opx_output" in result


class TestQubitPairWiring:
    """Test the qubit_pair_wiring function."""

    def test_basic_qubit_pair(self):
        """Test basic qubit pair wiring."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "octave"
        channel.io_type = "output"

        element_id = QubitPairReference(0, 1)

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_octave_port') as mock_create:
            mock_create.return_value = ("opx_output", "#/ports/port1")
            result = qubit_pair_wiring([channel], element_id)

        # Check for qubit references
        assert "control_qubit" in result
        assert result["control_qubit"] == "#/qubits/q0"
        assert "target_qubit" in result
        assert result["target_qubit"] == "#/qubits/q1"
        # Check for port
        assert "opx_output" in result
        assert result["opx_output"] == "#/ports/port1"

    def test_filters_digital_inputs(self):
        """Test that digital input channels are filtered out in qubit pairs."""
        digital_input = Mock(spec=AnyInstrumentChannel)
        digital_input.signal_type = "digital"
        digital_input.io_type = "input"

        element_id = QubitPairReference(2, 3)
        result = qubit_pair_wiring([digital_input], element_id)

        # Should only have qubit references, no port
        assert len(result) == 2
        assert "control_qubit" in result
        assert "target_qubit" in result


class TestGlobalElementWiring:
    """Test the global_element_wiring function."""

    def test_global_element_basic(self):
        """Test basic global element wiring."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "lf-fem"
        channel.io_type = "output"

        element_id = Mock(spec=ElementReference)
        element_id.value = "global1"
        line_type = WiringLineType.GLOBAL_GATE

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_lf_opx_plus_port') as mock_create:
            mock_create.return_value = ("opx_output", "#/ports/port1")
            result = global_element_wiring([channel], element_id, line_type)

        assert "opx_output" in result
        assert result["opx_output"] == "#/ports/port1"


class TestReadoutWiring:
    """Test the readout_wiring function."""

    def test_readout_basic(self):
        """Test basic readout wiring."""
        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "octave"
        channel.io_type = "output"

        element_id = Mock(spec=ElementReference)
        element_id.value = "readout1"
        line_type = WiringLineType.RF_RESONATOR

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_octave_port') as mock_create:
            mock_create.return_value = ("opx_output", "#/ports/port1")
            result = readout_wiring([channel], element_id, line_type)

        assert "opx_output" in result
        assert result["opx_output"] == "#/ports/port1"


class TestCreateWiring:
    """Test the main create_wiring function."""

    def test_resonator_line_type(self):
        """Test wiring creation for RESONATOR line type."""
        connectivity = Mock(spec=Connectivity)
        element = Mock()
        element_id = QubitReference(0)

        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "octave"
        channel.io_type = "output"

        element.channels = {WiringLineType.RESONATOR: [channel]}
        connectivity.elements = {element_id: element}

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_octave_port') as mock_create:
            mock_create.return_value = ("opx_output", "#/ports/port1")
            result = create_wiring(connectivity)

        # Check structure: qubits/q0/resonator/opx_output
        assert "qubits" in result
        assert "q0" in result["qubits"]
        assert "resonator" in result["qubits"]["q0"]
        assert "opx_output" in result["qubits"]["q0"]["resonator"]

    def test_coupler_line_type(self):
        """Test wiring creation for COUPLER line type."""
        connectivity = Mock(spec=Connectivity)
        element = Mock()
        element_id = QubitPairReference(0, 1)

        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "lf-fem"
        channel.io_type = "output"

        element.channels = {WiringLineType.COUPLER: [channel]}
        connectivity.elements = {element_id: element}

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_lf_opx_plus_port') as mock_create:
            mock_create.return_value = ("opx_output", "#/ports/port1")
            result = create_wiring(connectivity)

        # Check structure: qubit_pairs/q0_q1/coupler/...
        assert "qubit_pairs" in result
        assert "q0_q1" in result["qubit_pairs"]
        assert "coupler" in result["qubit_pairs"]["q0_q1"]

    def test_global_gate_line_type(self):
        """Test wiring creation for GLOBAL_GATE line type."""
        connectivity = Mock(spec=Connectivity)
        element = Mock()
        element_id = Mock(spec=ElementReference)
        element_id.value = "global1"

        channel = Mock(spec=AnyInstrumentChannel)
        channel.signal_type = "analog"
        channel.instrument_id = "lf-fem"
        channel.io_type = "output"

        element.channels = {WiringLineType.GLOBAL_GATE: [channel]}
        connectivity.elements = {element_id: element}

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_lf_opx_plus_port') as mock_create:
            mock_create.return_value = ("opx_output", "#/ports/port1")
            result = create_wiring(connectivity)

        # Check structure: globals/global1/global_gate/...
        assert "globals" in result

    def test_unknown_line_type_raises_error(self):
        """Test that unknown line types raise ValueError."""
        connectivity = Mock(spec=Connectivity)
        element = Mock()
        element_id = QubitReference(0)

        # Create a mock line type that's not in any of the known categories
        unknown_line_type = Mock()
        unknown_line_type.value = "unknown_type"

        element.channels = {unknown_line_type: []}
        connectivity.elements = {element_id: element}

        with pytest.raises(ValueError, match="Unknown line type"):
            create_wiring(connectivity)

    def test_multiple_line_types(self):
        """Test wiring creation with multiple line types."""
        connectivity = Mock(spec=Connectivity)
        element = Mock()
        element_id = QubitReference(0)

        drive_channel = Mock(spec=AnyInstrumentChannel)
        drive_channel.signal_type = "analog"
        drive_channel.instrument_id = "octave"
        drive_channel.io_type = "output"

        flux_channel = Mock(spec=AnyInstrumentChannel)
        flux_channel.signal_type = "analog"
        flux_channel.instrument_id = "lf-fem"
        flux_channel.io_type = "output"

        element.channels = {
            WiringLineType.DRIVE: [drive_channel],
            WiringLineType.FLUX: [flux_channel]
        }
        connectivity.elements = {element_id: element}

        with pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_octave_port') as mock_octave, \
             pytest.mock.patch('quam_builder.builder.qop_connectivity.create_wiring.create_lf_opx_plus_port') as mock_lf:
            mock_octave.return_value = ("opx_output", "#/ports/port1")
            mock_lf.return_value = ("opx_output", "#/ports/port2")
            result = create_wiring(connectivity)

        # Check that both line types are present
        assert "drive" in result["qubits"]["q0"]
        assert "flux" in result["qubits"]["q0"]