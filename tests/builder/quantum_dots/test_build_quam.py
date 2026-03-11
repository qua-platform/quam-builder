"""Tests for the build_quam function and related helpers.

Mock/patch policy:
- TestSetDefaultGridLocation, TestAddQPU: no mocks — pure functions or real objects.
- TestAddPorts: `machine.ports` is mocked because `add_ports` exercises
  the quam framework's port-resolution protocol (`reference_to_port`).
  Creating a real PortCollection with valid references requires the full
  wiring pipeline, which is already covered by the E2E tests.
- TestBuildQuam: `build_base_quam` and `build_loss_divincenzo_quam` are
  patched to test the *orchestration* logic of `build_quam` (correct
  call order, save flag forwarding) without re-executing the sub-builders
  that are independently tested.
- TestCalibrationPathResolver: the QuAM serializer is mocked because its
  real implementation requires a persisted state file on disk, which is
  irrelevant to the path-resolution logic under test.
- TestAddPulses: uses a real machine from the builder pipeline (no mocks).
"""

# pylint: disable=missing-class-docstring,missing-function-docstring,no-member

import shutil
import tempfile
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType

from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qpu.loss_divincenzo_quam import (
    LossDiVincenzoQuam,
)
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots.build_quam import (
    build_quam,
    build_base_quam,
    build_loss_divincenzo_quam,
    add_qpu,
    add_ports,
    add_pulses,
    _resolve_calibration_db_path,
    _set_default_grid_location,
)


class TestSetDefaultGridLocation:
    """Tests for the _set_default_grid_location helper function."""

    def test_single_qubit_location(self):
        location = _set_default_grid_location(0, 1)
        assert location == "0,0"

    def test_two_qubits_locations(self):
        loc0 = _set_default_grid_location(0, 2)
        loc1 = _set_default_grid_location(1, 2)
        assert loc0 == "0,0"
        assert loc1 == "0,1"

    def test_four_qubits_grid(self):
        locations = [_set_default_grid_location(i, 4) for i in range(4)]
        assert locations == ["0,0", "0,1", "1,0", "1,1"]

    def test_nine_qubits_grid(self):
        locations = [_set_default_grid_location(i, 9) for i in range(9)]
        assert locations == [
            "0,0",
            "0,1",
            "0,2",
            "1,0",
            "1,1",
            "1,2",
            "2,0",
            "2,1",
            "2,2",
        ]


class TestAddPorts:
    """Tests for the add_ports function.

    Uses a mock for machine.ports because add_ports calls the quam framework's
    reference_to_port protocol. The real PortCollection requires full wiring
    from the pipeline, already covered by E2E tests.
    """

    def test_add_ports_with_valid_wiring(self):
        machine = LossDiVincenzoQuam()
        machine.ports = MagicMock()

        class DummyRef(dict):
            def get_unreferenced_value(self, key):
                return self[key]

        machine.wiring = {
            "qubits": {
                "q1": {WiringLineType.DRIVE.value: DummyRef({"opx_output": "#/ports/con1/1"})}
            }
        }

        add_ports(machine)
        assert machine.ports.reference_to_port.called

    def test_add_ports_with_empty_wiring(self):
        machine = LossDiVincenzoQuam()
        machine.ports = MagicMock()
        machine.wiring = {}
        add_ports(machine)


class TestAddQPU:
    """Tests for the add_qpu function."""

    @pytest.fixture
    def machine_with_wiring(self):
        machine = LossDiVincenzoQuam()
        machine.wiring = {
            "qubits": {
                "q1": {
                    WiringLineType.PLUNGER_GATE.value: {
                        "opx_output": "#/wiring/qubits/q1/p/opx_output"
                    },
                    WiringLineType.DRIVE.value: {"opx_output": "#/ports/mw_outputs/con1/1/1"},
                },
                "q2": {
                    WiringLineType.PLUNGER_GATE.value: {
                        "opx_output": "#/wiring/qubits/q2/p/opx_output"
                    },
                    WiringLineType.DRIVE.value: {"opx_output": "#/ports/mw_outputs/con1/1/2"},
                },
            }
        }
        return machine

    def test_add_qpu_creates_virtual_gate_set(self, machine_with_wiring):
        add_qpu(machine_with_wiring)
        assert "main_qpu" in machine_with_wiring.virtual_gate_sets

    def test_add_qpu_registers_qubits(self, machine_with_wiring):
        add_qpu(machine_with_wiring)
        assert len(machine_with_wiring.qubits) > 0
        assert len(machine_with_wiring.quantum_dots) > 0

    def test_add_qpu_handles_sensor_dots(self):
        machine = BaseQuamQD()
        machine.wiring = {
            "sensor_dots": {
                "s1": {
                    WiringLineType.SENSOR_GATE.value: {
                        "opx_output": "#/wiring/sensor_dots/s1/s/opx_output"
                    },
                    WiringLineType.RF_RESONATOR.value: {
                        "opx_output": "#/wiring/sensor_dots/s1/rf/opx_output",
                        "opx_input": "#/wiring/sensor_dots/s1/rf/opx_input",
                    },
                }
            }
        }
        add_qpu(machine)
        assert len(machine.active_sensor_dot_names) > 0


class TestAddPulses:
    """Tests for the add_pulses function using a real machine from the pipeline."""

    @pytest.fixture
    def built_machine(self):
        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1])
        instruments.add_lf_fem(controller=1, slots=[2, 3])

        connectivity = Connectivity()
        connectivity.add_quantum_dots(
            quantum_dots=[1, 2],
            add_drive_lines=True,
            use_mw_fem=True,
            shared_drive_line=True,
        )
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2)])
        allocate_wiring(connectivity, instruments)

        tmp = tempfile.mkdtemp()
        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity,
            host_ip="127.0.0.1",
            cluster_name="test_cluster",
            quam_instance=machine,
            path=tmp,
        )
        machine = build_base_quam(machine, calibration_db_path=tmp, connect_qdac=False, save=False)
        machine = build_loss_divincenzo_quam(
            machine,
            implicit_mapping=True,
            save=False,
        )
        yield machine
        shutil.rmtree(tmp)

    def test_add_pulses_populates_xy_operations(self, built_machine):
        add_pulses(built_machine)
        for qubit in built_machine.qubits.values():
            if qubit.xy is not None:
                assert len(qubit.xy.operations) > 0

    def test_add_pulses_handles_empty_machine(self):
        machine = LossDiVincenzoQuam()
        machine.qubits = {}
        machine.qubit_pairs = {}
        add_pulses(machine)


class TestBuildQuam:
    """Tests for the build_quam orchestration.

    Patches build_base_quam and build_loss_divincenzo_quam to verify
    that build_quam delegates to them correctly and forwards the save flag.
    The sub-builders are independently tested elsewhere.
    """

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_build_quam_full_workflow(self, temp_dir):
        machine = LossDiVincenzoQuam()
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

        with (
            patch("quam_builder.builder.quantum_dots.build_quam.build_base_quam") as mock_base,
            patch(
                "quam_builder.builder.quantum_dots.build_quam.build_loss_divincenzo_quam"
            ) as mock_ld,
        ):
            mock_base.return_value = machine
            mock_ld.return_value = machine
            result = build_quam(machine, calibration_db_path=temp_dir, save=False)

        assert result is machine

    def test_build_quam_calls_all_functions(self, temp_dir):
        machine = BaseQuamQD()
        machine.wiring = {}
        machine.network = {"host": "127.0.0.1", "cluster_name": "test"}

        with (
            patch("quam_builder.builder.quantum_dots.build_quam.build_base_quam") as mock_base,
            patch(
                "quam_builder.builder.quantum_dots.build_quam.build_loss_divincenzo_quam"
            ) as mock_ld,
        ):
            mock_base.return_value = machine
            mock_ld.return_value = machine
            build_quam(machine, calibration_db_path=temp_dir)
            mock_base.assert_called_once()
            mock_ld.assert_called_once()

    def test_build_quam_saves_machine(self, temp_dir):
        machine = BaseQuamQD()
        machine.wiring = {}
        machine.network = {"host": "127.0.0.1", "cluster_name": "test"}

        with (
            patch("quam_builder.builder.quantum_dots.build_quam.build_base_quam") as mock_base,
            patch(
                "quam_builder.builder.quantum_dots.build_quam.build_loss_divincenzo_quam"
            ) as mock_ld,
        ):
            mock_base.return_value = machine
            mock_ld.return_value = machine
            build_quam(machine, calibration_db_path=temp_dir, save=True)
            assert mock_ld.call_args.kwargs["save"] is True

    def test_build_quam_can_skip_save(self, temp_dir):
        machine = BaseQuamQD()
        machine.wiring = {}
        machine.network = {"host": "127.0.0.1", "cluster_name": "test"}

        with (
            patch("quam_builder.builder.quantum_dots.build_quam.build_base_quam") as mock_base,
            patch(
                "quam_builder.builder.quantum_dots.build_quam.build_loss_divincenzo_quam"
            ) as mock_ld,
        ):
            mock_base.return_value = machine
            mock_ld.return_value = machine
            build_quam(machine, calibration_db_path=temp_dir, save=False)
            assert mock_ld.call_args.kwargs["save"] is False


class TestCalibrationPathResolver:
    """Tests for calibration path normalization.

    Mocks the QuAM serializer because its real implementation requires a
    persisted state file on disk, irrelevant to the path-resolution logic.
    """

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
