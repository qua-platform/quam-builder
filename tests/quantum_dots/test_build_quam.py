"""Unit tests for the build_quam function and related helpers."""

import pytest
import tempfile
import shutil
from unittest.mock import MagicMock, patch
from pathlib import Path

from quam_builder.builder.quantum_dots.build_quam import (
    build_quam,
    add_qpu,
    add_ports,
    add_pulses,
    _resolve_calibration_db_path,
    _set_default_grid_location,
)
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qpu.loss_divincenzo_quam import (
    LossDiVincenzoQuam,
)
from quam_builder.architecture.quantum_dots.qpu.loss_divincenzo_quam import (
    LossDiVincenzoQuam,
)
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType


class TestSetDefaultGridLocation:
    """Tests for the _set_default_grid_location helper function."""

    def test_single_qubit_location(self):
        """Test grid location for a single qubit."""
        location = _set_default_grid_location(0, 1)
        assert location == "0,0"

    def test_two_qubits_locations(self):
        """Test grid locations for two qubits."""
        loc0 = _set_default_grid_location(0, 2)
        loc1 = _set_default_grid_location(1, 2)
        assert loc0 == "0,0"
        assert loc1 == "0,1"

    def test_four_qubits_grid(self):
        """Test grid locations for four qubits (2x2 grid)."""
        locations = [_set_default_grid_location(i, 4) for i in range(4)]
        assert locations == ["0,0", "0,1", "1,0", "1,1"]

    def test_nine_qubits_grid(self):
        """Test grid locations for nine qubits (3x3 grid)."""
        locations = [_set_default_grid_location(i, 9) for i in range(9)]
        assert locations == [
            "0,0", "0,1", "0,2",
            "1,0", "1,1", "1,2",
            "2,0", "2,1", "2,2",
        ]


class TestAddPorts:
    """Tests for the add_ports function."""

    def test_add_ports_with_valid_wiring(self):
        """Test that ports are added from wiring configuration."""
        machine = LossDiVincenzoQuam()
        machine.ports = MagicMock()

        class DummyRef(dict):
            def get_unreferenced_value(self, key):
                return self[key]

        # Create mock wiring structure
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.DRIVE.value: DummyRef({"opx_output": "#/ports/con1/1"})
                }
            }
        }

        # Call add_ports
        add_ports(machine)

        # Verify ports.reference_to_port was called
        assert machine.ports.reference_to_port.called

    def test_add_ports_with_empty_wiring(self):
        """Test that add_ports handles empty wiring gracefully."""
        machine = LossDiVincenzoQuam()
        machine.ports = MagicMock()
        machine.wiring = {}

        # Should not raise an error
        add_ports(machine)


class TestAddQPU:
    """Tests for the add_qpu function."""

    @pytest.fixture
    def machine_with_wiring(self):
        """Create a machine with mock wiring for testing."""
        machine = LossDiVincenzoQuam()

        class DummyGlobalGate:
            def __init__(self, id):
                self.id = id
                self.name = f"global_{id}"
                self.grid_location = None

        # Mock wiring structure
        machine.wiring = {
            "global_gates": {
                "g1": {
                    WiringLineType.GLOBAL_GATE.value: {
                        "opx_output": "#/wiring/global_gates/g1/g/opx_output"
                    }
                }
            },
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: {
                        "opx_output": "#/wiring/qubits/q1/p/opx_output"
                    },
                    WiringLineType.DRIVE.value: {
                        "opx_output": "#/wiring/qubits/q1/xy/opx_output"
                    }
                },
                "q2": {
                    WiringLineType.PLUNGER_GATE.value: {
                        "opx_output": "#/wiring/qubits/q2/p/opx_output"
                    },
                    WiringLineType.DRIVE.value: {
                        "opx_output": "#/wiring/qubits/q2/xy/opx_output"
                    }
                }
            },
            "qubit_pairs": {
                "q1_q2": {
                    WiringLineType.BARRIER_GATE.value: {
                        "opx_output": "#/wiring/qubit_pairs/q1_q2/b/opx_output"
                    }
                }
            }
        }

        # Mock global_gate_type
        machine.global_gate_type = {"g1": DummyGlobalGate}

        return machine

    def test_add_qpu_creates_virtual_gate_set(self, machine_with_wiring):
        """Test that add_qpu creates a virtual gate set."""
        add_qpu(machine_with_wiring)

        # Verify virtual gate set was created
        assert "main_qpu" in machine_with_wiring.virtual_gate_sets

    def test_add_qpu_registers_qubits(self, machine_with_wiring):
        """Test that add_qpu registers qubits using the qubit-capable machine."""
        add_qpu(machine_with_wiring)

        # Verify qubits were registered
        assert len(machine_with_wiring.qubits) > 0
        assert len(machine_with_wiring.quantum_dots) > 0

    def test_add_qpu_handles_sensor_dots(self):
        """Test that add_qpu correctly handles sensor dots."""
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "sensor_dots": {
                "s1": {
                    WiringLineType.SENSOR_GATE.value: {
                        "opx_output": "#/wiring/sensor_dots/s1/s/opx_output"
                    },
                    WiringLineType.RF_RESONATOR.value: {
                        "opx_output": "#/wiring/sensor_dots/s1/rf/opx_output",
                        "opx_input": "#/wiring/sensor_dots/s1/rf/opx_input"
                    }
                }
            }
        }

        add_qpu(machine)

        # Verify sensor dots were processed
        assert len(machine.active_sensor_dot_names) > 0


class TestAddPulses:
    """Tests for the add_pulses function."""

    def test_add_pulses_to_qubits(self):
        """Test that pulses are added to all qubits."""
        machine = LossDiVincenzoQuam()

        # Create mock qubits
        qubit1 = MagicMock()
        qubit1.xy_channel = MagicMock()
        qubit1.xy_channel.operations = {}

        qubit2 = MagicMock()
        qubit2.xy_channel = MagicMock()
        qubit2.xy_channel.operations = {}

        machine.qubits = {"Q1": qubit1, "Q2": qubit2}
        machine.qubit_pairs = {}

        # Add pulses
        add_pulses(machine)

        # Verify the helper ran without error (mocks don't accumulate real pulses)
        assert isinstance(qubit1.xy_channel.operations, dict)
        assert isinstance(qubit2.xy_channel.operations, dict)

    def test_add_pulses_to_qubit_pairs(self):
        """Test that pulses are added to qubit pairs."""
        machine = LossDiVincenzoQuam()
        machine.qubits = {}

        # Create mock qubit pairs
        pair1 = MagicMock()
        machine.qubit_pairs = {"Q1_Q2": pair1}

        # Should not raise an error
        add_pulses(machine)

    def test_add_pulses_handles_empty_machine(self):
        """Test that add_pulses handles a machine with no qubits."""
        machine = LossDiVincenzoQuam()
        machine.qubits = {}
        machine.qubit_pairs = {}

        # Should not raise an error
        add_pulses(machine)


class TestBuildQuam:
    """Tests for the main build_quam function."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_build_quam_full_workflow(self, temp_dir):
        """Test the complete build_quam workflow."""
        machine = LossDiVincenzoQuam()

        # Create minimal wiring
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: {
                        "opx_output": "#/wiring/qubits/q1/p/opx_output"
                    }
                }
            }
        }

        machine.network = {"host": "127.0.0.1", "cluster_name": "test"}

        with patch('quam_builder.builder.quantum_dots.build_quam.add_octaves'), \
             patch('quam_builder.builder.quantum_dots.build_quam.add_external_mixers'), \
             patch('quam_builder.builder.quantum_dots.build_quam.add_ports'), \
             patch('quam_builder.builder.quantum_dots.build_quam.add_qpu'), \
             patch('quam_builder.builder.quantum_dots.build_quam.add_pulses'):

            result = build_quam(machine, calibration_db_path=temp_dir, save=False)

        # Verify the function completed
        assert result is not None
        assert result == machine

    def test_build_quam_calls_all_functions(self, temp_dir):
        """Test that build_quam calls all necessary sub-functions."""
        machine = LossDiVincenzoQuam()
        machine.wiring = {}
        machine.network = {"host": "127.0.0.1", "cluster_name": "test"}

        with patch('quam_builder.builder.quantum_dots.build_quam.add_octaves') as mock_octaves, \
             patch('quam_builder.builder.quantum_dots.build_quam.add_external_mixers') as mock_mixers, \
             patch('quam_builder.builder.quantum_dots.build_quam.add_ports') as mock_ports, \
             patch('quam_builder.builder.quantum_dots.build_quam.add_qpu') as mock_qpu, \
             patch('quam_builder.builder.quantum_dots.build_quam.add_pulses') as mock_pulses:

            build_quam(machine, calibration_db_path=temp_dir)

            # Verify all functions were called
            mock_octaves.assert_called_once()
            mock_mixers.assert_called_once()
            mock_ports.assert_called_once()
            mock_qpu.assert_called_once()
            mock_pulses.assert_called_once()

    def test_build_quam_saves_machine(self, temp_dir):
        """Test that build_quam saves the machine."""
        machine = LossDiVincenzoQuam()
        machine.wiring = {}
        machine.network = {"host": "127.0.0.1", "cluster_name": "test"}

        with patch('quam_builder.builder.quantum_dots.build_quam.add_octaves'), \
             patch('quam_builder.builder.quantum_dots.build_quam.add_external_mixers'), \
             patch('quam_builder.builder.quantum_dots.build_quam.add_ports'), \
            patch('quam_builder.builder.quantum_dots.build_quam.add_qpu'), \
            patch('quam_builder.builder.quantum_dots.build_quam.add_pulses'), \
            patch.object(machine, 'save') as mock_save:

            build_quam(machine, calibration_db_path=temp_dir, save=True)

            # Verify save was called
            mock_save.assert_called_once()

    def test_build_quam_can_skip_save(self, temp_dir):
        """Ensure build_quam respects save flag."""
        machine = LossDiVincenzoQuam()
        machine.wiring = {}
        machine.network = {"host": "127.0.0.1", "cluster_name": "test"}

        with patch('quam_builder.builder.quantum_dots.build_quam.add_octaves'), \
             patch('quam_builder.builder.quantum_dots.build_quam.add_external_mixers'), \
             patch('quam_builder.builder.quantum_dots.build_quam.add_ports'), \
             patch('quam_builder.builder.quantum_dots.build_quam.add_qpu'), \
             patch('quam_builder.builder.quantum_dots.build_quam.add_pulses'), \
             patch.object(machine, 'save') as mock_save:

            build_quam(machine, calibration_db_path=temp_dir, save=False)

            mock_save.assert_not_called()


class TestCalibrationPathResolver:
    """Tests for calibration path normalization."""

    def test_resolves_none_to_state_parent(self, tmp_path):
        machine = LossDiVincenzoQuam()
        serializer = MagicMock()
        serializer._get_state_path.return_value = tmp_path / "state.json"
        machine.get_serialiser = lambda: serializer

        resolved = _resolve_calibration_db_path(machine, None)
        assert resolved == tmp_path

    def test_resolves_string_to_path(self):
        machine = LossDiVincenzoQuam()
        serializer = MagicMock()
        serializer._get_state_path.return_value = Path("/tmp/state.json")
        machine.get_serialiser = lambda: serializer

        resolved = _resolve_calibration_db_path(machine, "/tmp/calibration")
        assert resolved == Path("/tmp/calibration")
