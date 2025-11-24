"""
Comprehensive tests for build_quam_wiring functionality.
Tests the main wiring builder and helper functions.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from qualang_tools.wirer import Connectivity
from qualang_tools.wirer.instruments.instrument_channel import AnyInstrumentChannel
from qualang_tools.wirer.connectivity.element import QubitReference
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam.components.ports import FEMPortsContainer, OPXPlusPortsContainer

from quam_builder.builder.qop_connectivity.build_quam_wiring import (
    build_quam_wiring,
    add_ports_container,
    add_name_and_ip,
)


class TestAddPortsContainer:
    """Test the add_ports_container function."""

    def test_lf_fem_instrument_adds_fem_container(self):
        """Test that LF-FEM instrument adds FEMPortsContainer."""
        connectivity = Mock(spec=Connectivity)
        machine = Mock()

        # Create mock element with LF-FEM channel
        element = Mock()
        channel = Mock(spec=AnyInstrumentChannel)
        channel.instrument_id = "lf-fem"

        element.channels = {WiringLineType.FLUX: [channel]}
        connectivity.elements = {QubitReference(0): element}

        add_ports_container(connectivity, machine)

        assert isinstance(machine.ports, FEMPortsContainer)

    def test_mw_fem_instrument_adds_fem_container(self):
        """Test that MW-FEM instrument adds FEMPortsContainer."""
        connectivity = Mock(spec=Connectivity)
        machine = Mock()

        # Create mock element with MW-FEM channel
        element = Mock()
        channel = Mock(spec=AnyInstrumentChannel)
        channel.instrument_id = "mw-fem"

        element.channels = {WiringLineType.DRIVE: [channel]}
        connectivity.elements = {QubitReference(0): element}

        add_ports_container(connectivity, machine)

        assert isinstance(machine.ports, FEMPortsContainer)

    def test_opx_plus_instrument_adds_opx_plus_container(self):
        """Test that OPX+ instrument adds OPXPlusPortsContainer."""
        connectivity = Mock(spec=Connectivity)
        machine = Mock()

        # Create mock element with OPX+ channel
        element = Mock()
        channel = Mock(spec=AnyInstrumentChannel)
        channel.instrument_id = "opx+"

        element.channels = {WiringLineType.FLUX: [channel]}
        connectivity.elements = {QubitReference(0): element}

        add_ports_container(connectivity, machine)

        assert isinstance(machine.ports, OPXPlusPortsContainer)

    def test_multiple_elements_lf_fem_takes_precedence(self):
        """Test that when multiple instruments exist, LF-FEM takes precedence."""
        connectivity = Mock(spec=Connectivity)
        machine = Mock()

        # Create first element with LF-FEM
        element1 = Mock()
        channel1 = Mock(spec=AnyInstrumentChannel)
        channel1.instrument_id = "lf-fem"
        element1.channels = {WiringLineType.FLUX: [channel1]}

        # Create second element with OPX+
        element2 = Mock()
        channel2 = Mock(spec=AnyInstrumentChannel)
        channel2.instrument_id = "opx+"
        element2.channels = {WiringLineType.FLUX: [channel2]}

        connectivity.elements = {
            QubitReference(0): element1,
            QubitReference(1): element2
        }

        add_ports_container(connectivity, machine)

        # LF-FEM should override OPX+
        assert isinstance(machine.ports, FEMPortsContainer)

    def test_empty_connectivity(self):
        """Test with empty connectivity object."""
        connectivity = Mock(spec=Connectivity)
        connectivity.elements = {}
        machine = Mock()

        # Should not raise error, just not set ports
        add_ports_container(connectivity, machine)

        # ports should not be set
        assert not hasattr(machine, 'ports') or machine.ports is None or isinstance(machine.ports, Mock)

    def test_multiple_channels_same_element(self):
        """Test element with multiple channels of same instrument type."""
        connectivity = Mock(spec=Connectivity)
        machine = Mock()

        element = Mock()
        channel1 = Mock(spec=AnyInstrumentChannel)
        channel1.instrument_id = "mw-fem"

        channel2 = Mock(spec=AnyInstrumentChannel)
        channel2.instrument_id = "mw-fem"

        element.channels = {
            WiringLineType.DRIVE: [channel1],
            WiringLineType.RESONATOR: [channel2]
        }
        connectivity.elements = {QubitReference(0): element}

        add_ports_container(connectivity, machine)

        assert isinstance(machine.ports, FEMPortsContainer)


class TestAddNameAndIp:
    """Test the add_name_and_ip function."""

    def test_basic_network_info(self):
        """Test adding basic network information."""
        machine = Mock()
        host_ip = "192.168.1.100"
        cluster_name = "TestCluster"
        port = 9510

        add_name_and_ip(machine, host_ip, cluster_name, port)

        assert machine.network == {
            "host": "192.168.1.100",
            "port": 9510,
            "cluster_name": "TestCluster"
        }

    def test_localhost_ip(self):
        """Test with localhost IP."""
        machine = Mock()
        host_ip = "127.0.0.1"
        cluster_name = "LocalCluster"
        port = 80

        add_name_and_ip(machine, host_ip, cluster_name, port)

        assert machine.network["host"] == "127.0.0.1"
        assert machine.network["cluster_name"] == "LocalCluster"
        assert machine.network["port"] == 80

    def test_none_port(self):
        """Test with None port value."""
        machine = Mock()
        host_ip = "10.0.0.1"
        cluster_name = "Cluster_1"
        port = None

        add_name_and_ip(machine, host_ip, cluster_name, port)

        assert machine.network["host"] == "10.0.0.1"
        assert machine.network["port"] is None
        assert machine.network["cluster_name"] == "Cluster_1"

    def test_different_cluster_names(self):
        """Test with different cluster name formats."""
        machine = Mock()
        host_ip = "192.168.1.1"
        port = 9510

        # Test with underscores
        add_name_and_ip(machine, host_ip, "Test_Cluster_1", port)
        assert machine.network["cluster_name"] == "Test_Cluster_1"

        # Test with spaces (if allowed)
        add_name_and_ip(machine, host_ip, "Test Cluster", port)
        assert machine.network["cluster_name"] == "Test Cluster"

        # Test with special characters
        add_name_and_ip(machine, host_ip, "Cluster-2023", port)
        assert machine.network["cluster_name"] == "Cluster-2023"


class TestBuildQuamWiring:
    """Test the main build_quam_wiring function."""

    @patch('quam_builder.builder.qop_connectivity.build_quam_wiring.create_wiring')
    def test_basic_build_wiring(self, mock_create_wiring):
        """Test basic wiring build with all components."""
        connectivity = Mock(spec=Connectivity)
        quam_instance = Mock()

        # Setup connectivity with LF-FEM
        element = Mock()
        channel = Mock(spec=AnyInstrumentChannel)
        channel.instrument_id = "lf-fem"
        element.channels = {WiringLineType.FLUX: [channel]}
        connectivity.elements = {QubitReference(0): element}

        # Setup mock return value
        mock_wiring_dict = {"qubits": {"q0": {"flux": {}}}}
        mock_create_wiring.return_value = mock_wiring_dict

        host_ip = "192.168.1.100"
        cluster_name = "TestCluster"

        build_quam_wiring(connectivity, host_ip, cluster_name, quam_instance)

        # Verify ports container was added
        assert isinstance(quam_instance.ports, FEMPortsContainer)

        # Verify network info was added
        assert quam_instance.network == {
            "host": "192.168.1.100",
            "port": None,
            "cluster_name": "TestCluster"
        }

        # Verify wiring was created and assigned
        mock_create_wiring.assert_called_once_with(connectivity)
        assert quam_instance.wiring == mock_wiring_dict

        # Verify save was called
        quam_instance.save.assert_called_once()

    @patch('quam_builder.builder.qop_connectivity.build_quam_wiring.create_wiring')
    def test_build_wiring_with_port(self, mock_create_wiring):
        """Test wiring build with custom port."""
        connectivity = Mock(spec=Connectivity)
        quam_instance = Mock()

        element = Mock()
        channel = Mock(spec=AnyInstrumentChannel)
        channel.instrument_id = "mw-fem"
        element.channels = {WiringLineType.DRIVE: [channel]}
        connectivity.elements = {QubitReference(0): element}

        mock_create_wiring.return_value = {"qubits": {}}

        host_ip = "10.0.0.1"
        cluster_name = "Cluster_1"
        port = 8080

        build_quam_wiring(connectivity, host_ip, cluster_name, quam_instance, port=port)

        # Verify port was set correctly
        assert quam_instance.network["port"] == 8080

        quam_instance.save.assert_called_once()

    @patch('quam_builder.builder.qop_connectivity.build_quam_wiring.create_wiring')
    def test_build_wiring_opx_plus(self, mock_create_wiring):
        """Test wiring build with OPX+ instrument."""
        connectivity = Mock(spec=Connectivity)
        quam_instance = Mock()

        element = Mock()
        channel = Mock(spec=AnyInstrumentChannel)
        channel.instrument_id = "opx+"
        element.channels = {WiringLineType.FLUX: [channel]}
        connectivity.elements = {QubitReference(0): element}

        mock_create_wiring.return_value = {"qubits": {}}

        build_quam_wiring(connectivity, "192.168.1.1", "OPXCluster", quam_instance)

        # Verify OPX+ container was added
        assert isinstance(quam_instance.ports, OPXPlusPortsContainer)

        quam_instance.save.assert_called_once()

    @patch('quam_builder.builder.qop_connectivity.build_quam_wiring.create_wiring')
    def test_build_wiring_call_order(self, mock_create_wiring):
        """Test that functions are called in correct order."""
        connectivity = Mock(spec=Connectivity)
        quam_instance = Mock()

        element = Mock()
        channel = Mock(spec=AnyInstrumentChannel)
        channel.instrument_id = "lf-fem"
        element.channels = {WiringLineType.FLUX: [channel]}
        connectivity.elements = {QubitReference(0): element}

        mock_create_wiring.return_value = {"qubits": {}}

        # Track call order
        call_order = []

        def track_ports_set(*args, **kwargs):
            call_order.append("ports")
            return FEMPortsContainer()

        def track_network_set(*args, **kwargs):
            call_order.append("network")

        def track_wiring_set(*args, **kwargs):
            call_order.append("wiring")
            return {"qubits": {}}

        def track_save(*args, **kwargs):
            call_order.append("save")

        # Use property setters to track calls
        type(quam_instance).ports = property(fset=lambda self, val: call_order.append("ports"))
        type(quam_instance).network = property(fset=lambda self, val: call_order.append("network"))
        type(quam_instance).wiring = property(fset=lambda self, val: call_order.append("wiring"))
        quam_instance.save = Mock(side_effect=track_save)

        build_quam_wiring(connectivity, "192.168.1.1", "Cluster", quam_instance)

        # Verify save was called last
        assert call_order[-1] == "save"

    @patch('quam_builder.builder.qop_connectivity.build_quam_wiring.create_wiring')
    def test_build_wiring_preserves_existing_attributes(self, mock_create_wiring):
        """Test that building wiring doesn't delete other machine attributes."""
        connectivity = Mock(spec=Connectivity)
        quam_instance = Mock()

        # Set some existing attributes
        quam_instance.qubits = {"q0": "existing_qubit"}
        quam_instance.other_config = "some_value"

        element = Mock()
        channel = Mock(spec=AnyInstrumentChannel)
        channel.instrument_id = "lf-fem"
        element.channels = {WiringLineType.FLUX: [channel]}
        connectivity.elements = {QubitReference(0): element}

        mock_create_wiring.return_value = {"qubits": {}}

        build_quam_wiring(connectivity, "192.168.1.1", "Cluster", quam_instance)

        # Verify existing attributes are preserved
        assert quam_instance.qubits == {"q0": "existing_qubit"}
        assert quam_instance.other_config == "some_value"


class TestIntegrationScenarios:
    """Integration tests for realistic build scenarios."""

    @patch('quam_builder.builder.qop_connectivity.build_quam_wiring.create_wiring')
    def test_full_quantum_dot_system(self, mock_create_wiring):
        """Test building wiring for a complete quantum dot system."""
        connectivity = Mock(spec=Connectivity)
        quam_instance = Mock()

        # Create multiple elements with different instrument types
        elements = {}

        # Qubit 0 with MW-FEM and LF-FEM
        q0_element = Mock()
        mw_channel = Mock(spec=AnyInstrumentChannel)
        mw_channel.instrument_id = "mw-fem"
        lf_channel = Mock(spec=AnyInstrumentChannel)
        lf_channel.instrument_id = "lf-fem"

        q0_element.channels = {
            WiringLineType.DRIVE: [mw_channel],
            WiringLineType.FLUX: [lf_channel]
        }
        elements[QubitReference(0)] = q0_element

        # Qubit 1
        q1_element = Mock()
        q1_element.channels = {WiringLineType.DRIVE: [mw_channel]}
        elements[QubitReference(1)] = q1_element

        connectivity.elements = elements

        mock_wiring = {
            "qubits": {
                "q0": {"drive": {}, "flux": {}},
                "q1": {"drive": {}}
            }
        }
        mock_create_wiring.return_value = mock_wiring

        build_quam_wiring(
            connectivity,
            "127.0.0.1",
            "QuantumDot_Cluster",
            quam_instance,
            port=9510
        )

        # Verify all components were set up
        assert isinstance(quam_instance.ports, FEMPortsContainer)
        assert quam_instance.network["host"] == "127.0.0.1"
        assert quam_instance.network["port"] == 9510
        assert quam_instance.network["cluster_name"] == "QuantumDot_Cluster"
        assert quam_instance.wiring == mock_wiring

        mock_create_wiring.assert_called_once_with(connectivity)
        quam_instance.save.assert_called_once()

    @patch('quam_builder.builder.qop_connectivity.build_quam_wiring.create_wiring')
    def test_minimal_single_qubit_system(self, mock_create_wiring):
        """Test building wiring for a minimal single qubit system."""
        connectivity = Mock(spec=Connectivity)
        quam_instance = Mock()

        element = Mock()
        channel = Mock(spec=AnyInstrumentChannel)
        channel.instrument_id = "opx+"
        element.channels = {WiringLineType.DRIVE: [channel]}
        connectivity.elements = {QubitReference(0): element}

        mock_create_wiring.return_value = {"qubits": {"q0": {"drive": {}}}}

        build_quam_wiring(connectivity, "127.0.0.1", "MinimalSystem", quam_instance)

        assert isinstance(quam_instance.ports, OPXPlusPortsContainer)
        assert quam_instance.wiring == {"qubits": {"q0": {"drive": {}}}}
        quam_instance.save.assert_called_once()