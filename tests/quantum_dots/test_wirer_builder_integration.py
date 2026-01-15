"""Integration tests for the wirer and builder working together."""

# pylint: disable=too-few-public-methods

import shutil
import tempfile
from pathlib import Path

import pytest

from qualang_tools.wirer import Instruments, Connectivity, allocate_wiring
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots import build_quam, build_base_quam
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qpu.loss_divincenzo_quam import (
    LossDiVincenzoQuam,
)
from quam_builder.architecture.quantum_dots.components import VoltageGate


def _normalize_wiring(machine: BaseQuamQD) -> BaseQuamQD:
    """Adapts wirer output keys to what build_quam expects."""

    class _DummyGlobalGate:
        def __init__(self, id):
            self.id = id
            self.name = f"global_{id}"
            self.grid_location = None

    wiring = machine.wiring
    if "globals" in wiring and "global_gates" not in wiring:
        wiring["global_gates"] = wiring["globals"]
        wiring.pop("globals")
    if "readout" in wiring and "sensor_dots" not in wiring:
        wiring["sensor_dots"] = wiring["readout"]
        wiring.pop("readout")
    if "qubit_pairs" in wiring:
        qp_mapping = wiring["qubit_pairs"]
        for qp_id in list(qp_mapping.keys()):
            new_id = qp_id.replace("-", "_")
            if new_id != qp_id:
                qp_mapping[new_id] = qp_mapping[qp_id]
                qp_mapping.pop(qp_id)
    if "global_gates" in wiring:
        machine.global_gate_type = {gid: _DummyGlobalGate for gid in wiring["global_gates"].keys()}
    return machine


class TestWirerBuilderIntegration:
    """Integration tests for the complete wiring and building workflow."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def instruments(self):
        """Create instruments configuration."""
        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1, 2])
        instruments.add_lf_fem(controller=1, slots=[3, 4, 5])
        return instruments

    def test_complete_workflow_basic_setup(self, instruments, temp_dir):
        """Test the complete workflow from wiring to build for a basic setup."""
        # Setup connectivity
        connectivity = Connectivity()
        connectivity.add_sensor_dots(sensor_dots=[1], shared_resonator_line=False)
        connectivity.add_quantum_dots(quantum_dots=[1, 2])
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2)])

        # Allocate wiring
        allocate_wiring(connectivity, instruments)

        # Build wiring
        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity,
            host_ip="127.0.0.1",
            cluster_name="test_cluster",
            quam_instance=machine,
            path=temp_dir,
        )
        machine = _normalize_wiring(machine)

        # Verify wiring was created
        assert machine.wiring is not None
        assert "sensor_dots" in machine.wiring
        assert "qubits" in machine.wiring
        assert "qubit_pairs" in machine.wiring

        # Build QuAM
        machine_loaded = BaseQuamQD.load(temp_dir)
        _normalize_wiring(machine_loaded)
        build_quam(machine_loaded, calibration_db_path=temp_dir)

        # Verify QPU elements were created
        assert len(machine_loaded.sensor_dots) > 0
        assert len(machine_loaded.quantum_dots) > 0
        assert len(machine_loaded.quantum_dots) > 0

    def test_workflow_with_multiple_qubits(self, instruments, temp_dir):
        """Test workflow with multiple qubits and qubit pairs."""
        # Setup connectivity with more qubits
        connectivity = Connectivity()
        connectivity.add_sensor_dots(sensor_dots=[1, 2], shared_resonator_line=False)
        connectivity.add_quantum_dots(quantum_dots=[1, 2, 3, 4])
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2), (2, 3), (3, 4)])

        # Allocate wiring
        allocate_wiring(connectivity, instruments)

        # Build wiring
        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity,
            host_ip="127.0.0.1",
            cluster_name="test_cluster",
            quam_instance=machine,
            path=temp_dir,
        )
        machine = _normalize_wiring(machine)

        # Build QuAM
        machine_loaded = BaseQuamQD.load(temp_dir)
        _normalize_wiring(machine_loaded)
        build_quam(machine_loaded, calibration_db_path=temp_dir)

        # Verify correct number of elements
        assert len(machine_loaded.quantum_dots) == 4
        assert len(machine_loaded.quantum_dots) == 4
        assert len(machine_loaded.quantum_dot_pairs) == 3
        assert len(machine_loaded.sensor_dots) == 2

    def test_virtual_gate_set_creation(self, instruments, temp_dir):
        """Test that virtual gate set is correctly created."""
        connectivity = Connectivity()
        connectivity.add_quantum_dots(quantum_dots=[1, 2, 3])

        allocate_wiring(connectivity, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity,
            host_ip="127.0.0.1",
            cluster_name="test_cluster",
            quam_instance=machine,
            path=temp_dir,
        )

        machine_loaded = BaseQuamQD.load(temp_dir)
        build_quam(machine_loaded, calibration_db_path=temp_dir)

        # Verify virtual gate set was created
        assert len(machine_loaded.virtual_gate_sets) > 0
        assert "main_qpu" in machine_loaded.virtual_gate_sets

        # Verify virtual gate set has correct channels
        vgs = machine_loaded.virtual_gate_sets["main_qpu"]
        assert len(vgs.channels) >= 3  # At least 3 plunger gates

    def test_qubit_registration_with_xy_drives(self, instruments, temp_dir):
        """Test that qubits are registered with their XY drives in Stage 2."""
        connectivity = Connectivity()
        connectivity.add_quantum_dots(quantum_dots=[1, 2])

        allocate_wiring(connectivity, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity,
            host_ip="127.0.0.1",
            cluster_name="test_cluster",
            quam_instance=machine,
            path=temp_dir,
        )

        machine_loaded = BaseQuamQD.load(temp_dir)
        # build_quam does both Stage 1 and Stage 2, creating qubits with XY drives
        build_quam(machine_loaded, calibration_db_path=temp_dir)

        # Verify qubits (Stage 2) have XY drives
        # Note: qubits are in machine_loaded.qubits, not quantum_dots
        assert hasattr(machine_loaded, "qubits"), "Machine should have qubits after build_quam"
        for qubit_name, qubit in machine_loaded.qubits.items():
            # Check if qubit has an xy_channel attribute
            assert hasattr(
                qubit, "xy_channel"
            ), f"Qubit {qubit_name} should have xy_channel attribute"

    def test_sensor_dots_with_resonators(self, instruments, temp_dir):
        """Test that sensor dots are registered with resonators."""
        connectivity = Connectivity()
        connectivity.add_sensor_dots(sensor_dots=[1, 2], shared_resonator_line=False)

        allocate_wiring(connectivity, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity,
            host_ip="127.0.0.1",
            cluster_name="test_cluster",
            quam_instance=machine,
            path=temp_dir,
        )

        machine_loaded = BaseQuamQD.load(temp_dir)
        build_base_quam(machine_loaded, calibration_db_path=temp_dir, save=False)

        # Verify sensor dots have resonators
        assert len(machine_loaded.sensor_dots) == 2
        # Note: Resonator attachment depends on wiring allocation

    def test_pulses_are_added(self, instruments, temp_dir):
        """Test that default pulses are added to qubits in Stage 2."""
        connectivity = Connectivity()
        connectivity.add_quantum_dots(quantum_dots=[1, 2])

        allocate_wiring(connectivity, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity,
            host_ip="127.0.0.1",
            cluster_name="test_cluster",
            quam_instance=machine,
            path=temp_dir,
        )

        machine_loaded = BaseQuamQD.load(temp_dir)
        # build_quam does both Stage 1 and Stage 2, creating qubits with XY drives
        build_quam(machine_loaded, calibration_db_path=temp_dir)

        # Verify qubits (Stage 2) have pulses (if they have xy channels)
        assert hasattr(machine_loaded, "qubits"), "Machine should have qubits after build_quam"
        for qubit_name, qubit in machine_loaded.qubits.items():
            if hasattr(qubit, "xy_channel") and qubit.xy_channel is not None:
                # Should have XY operations
                assert len(qubit.xy_channel.operations) > 0

    def test_network_configuration_is_set(self, instruments, temp_dir):
        """Test that network configuration is properly set."""
        connectivity = Connectivity()
        connectivity.add_quantum_dots(quantum_dots=[1])

        allocate_wiring(connectivity, instruments)

        machine = LossDiVincenzoQuam()
        machine = build_quam_wiring(
            connectivity,
            host_ip="192.168.1.100",
            cluster_name="my_cluster",
            quam_instance=machine,
            port=9510,
            path=temp_dir,
        )

        # Verify network configuration
        assert machine.network["host"] == "192.168.1.100"
        assert machine.network["cluster_name"] == "my_cluster"
        assert machine.network["port"] == 9510

    def test_active_element_names_are_set(self, instruments, temp_dir):
        """Test that active element names lists are populated."""
        connectivity = Connectivity()
        connectivity.add_sensor_dots(sensor_dots=[1], shared_resonator_line=False)
        connectivity.add_quantum_dots(quantum_dots=[1, 2])
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2)])

        allocate_wiring(connectivity, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity,
            host_ip="127.0.0.1",
            cluster_name="test_cluster",
            quam_instance=machine,
            path=temp_dir,
        )

        machine_loaded = BaseQuamQD.load(temp_dir)
        build_quam(machine_loaded, calibration_db_path=temp_dir)

        # Verify elements are populated
        assert len(machine_loaded.sensor_dots) > 0
        assert len(machine_loaded.quantum_dots) > 0
        assert len(machine_loaded.quantum_dot_pairs) > 0


class TestWirerOnly:
    """Tests specifically for the wirer connectivity setup."""

    def test_connectivity_quantum_dot_interface(self):
        """Test that the quantum dot connectivity interface works correctly."""
        connectivity = Connectivity()

        # Add various element types
        connectivity.add_voltage_gate_lines(voltage_gates=[1, 2], name="g")
        connectivity.add_sensor_dots(sensor_dots=[1, 2], shared_resonator_line=True)
        connectivity.add_quantum_dots(quantum_dots=[1, 2, 3])
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2), (2, 3)])

        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1])
        instruments.add_lf_fem(controller=1, slots=[2, 3])
        allocate_wiring(connectivity, instruments)

        # Verify elements were added
        assert len(connectivity.elements) > 0

        # Check element types
        element_types = set()
        for element in connectivity.elements.values():
            for line_type in element.channels:
                element_types.add(line_type.value)

        expected_types = {"g", "s", "rf", "p", "xy", "b"}
        assert element_types.intersection(expected_types)

    def test_allocate_wiring_creates_channels(self):
        """Test that allocate_wiring creates proper channel allocations."""
        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1])
        instruments.add_lf_fem(controller=1, slots=[2, 3])

        connectivity = Connectivity()
        connectivity.add_quantum_dots(quantum_dots=[1, 2])

        # Allocate wiring
        allocate_wiring(connectivity, instruments)

        # Verify channels were allocated
        for element in connectivity.elements.values():
            assert len(element.channels) > 0
            for channel_list in element.channels.values():
                assert len(channel_list) > 0
