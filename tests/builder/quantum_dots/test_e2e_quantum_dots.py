"""End-to-end tests for quantum dots QUAM construction using the wiring tools.

Tests the full workflow from instrument definition → connectivity setup →
wiring allocation → QUAM construction for quantum dot architectures
(combined, two-stage, incremental drive-line workflows).

These tests exercise the interoperability with py-qua-tools (qualang-tools)
wiring infrastructure.
"""

# pylint: disable=no-member

import shutil
import tempfile

import pytest
from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring

from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qpu.loss_divincenzo_quam import (
    LossDiVincenzoQuam,
)
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots import (
    build_base_quam,
    build_loss_divincenzo_quam,
    build_quam as build_quam_qd,
)


@pytest.fixture
def temp_dir():
    """Create and clean up a temporary directory for test artifacts."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


class TestQuantumDotsCombinedWorkflow:
    """Combined single-stage workflow for quantum dots (mirrors example_2)."""

    @pytest.fixture
    def instruments(self):
        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1])
        instruments.add_lf_fem(controller=1, slots=[2, 3])
        return instruments

    def test_five_dot_combined_build(self, instruments, temp_dir):
        """5 quantum dots, 2 sensors, 2 global gates — combined workflow."""
        global_gates = [1, 2]
        sensor_dots = [1, 2]
        quantum_dots = [1, 2, 3, 4, 5]
        quantum_dot_pairs = [(1, 2), (2, 3), (3, 4), (4, 5)]
        qubit_pair_sensor_map = {
            "q1_q2": ["sensor_1"],
            "q2_q3": ["sensor_1", "sensor_2"],
            "q3_q4": ["sensor_2"],
        }

        connectivity = Connectivity()
        connectivity.add_voltage_gate_lines(voltage_gates=global_gates, name="rb")
        connectivity.add_sensor_dots(
            sensor_dots=sensor_dots, shared_resonator_line=False, use_mw_fem=False
        )
        connectivity.add_quantum_dots(
            quantum_dots=quantum_dots,
            add_drive_lines=True,
            use_mw_fem=True,
            shared_drive_line=True,
        )
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=quantum_dot_pairs)
        allocate_wiring(connectivity, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir
        )
        machine = build_quam_qd(
            machine,
            calibration_db_path=temp_dir,
            qubit_pair_sensor_map=qubit_pair_sensor_map,
            connect_qdac=False,
            save=False,
        )

        assert isinstance(machine, LossDiVincenzoQuam)
        assert len(machine.quantum_dots) == 5
        assert len(machine.sensor_dots) == 2
        assert len(machine.qubits) == 5
        assert len(machine.quantum_dot_pairs) == 4
        assert len(machine.virtual_gate_sets) > 0

    def test_two_dot_minimal(self, instruments, temp_dir):
        """Minimal 2-dot system without global gates."""
        connectivity = Connectivity()
        connectivity.add_sensor_dots(sensor_dots=[1], shared_resonator_line=False, use_mw_fem=False)
        connectivity.add_quantum_dots(
            quantum_dots=[1, 2],
            add_drive_lines=True,
            use_mw_fem=True,
            shared_drive_line=True,
        )
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2)])
        allocate_wiring(connectivity, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir
        )
        machine = build_quam_qd(
            machine,
            calibration_db_path=temp_dir,
            connect_qdac=False,
            save=False,
        )

        assert len(machine.quantum_dots) == 2
        assert len(machine.sensor_dots) == 1
        assert len(machine.qubits) == 2


class TestQuantumDotsTwoStageWorkflow:
    """Two-stage workflow: dot layer first, then qubits (mirrors example_1)."""

    GLOBAL_GATES = [1]
    SENSOR_DOTS = [1, 2]
    QUANTUM_DOTS = [1, 2, 3]
    QUANTUM_DOT_PAIRS = [(1, 2), (2, 3)]

    @staticmethod
    def _make_stage1_connectivity(global_gates, sensor_dots, quantum_dots, dot_pairs):
        connectivity = Connectivity()
        connectivity.add_voltage_gate_lines(voltage_gates=global_gates, name="rb")
        connectivity.add_sensor_dots(
            sensor_dots=sensor_dots, shared_resonator_line=False, use_mw_fem=False
        )
        connectivity.add_quantum_dots(quantum_dots=quantum_dots, add_drive_lines=False)
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=dot_pairs)
        return connectivity

    @staticmethod
    def _make_stage2_connectivity(global_gates, sensor_dots, quantum_dots, dot_pairs):
        connectivity = Connectivity()
        connectivity.add_voltage_gate_lines(voltage_gates=global_gates, name="rb")
        connectivity.add_sensor_dots(
            sensor_dots=sensor_dots, shared_resonator_line=False, use_mw_fem=False
        )
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=dot_pairs)
        connectivity.add_quantum_dots(
            quantum_dots=quantum_dots,
            add_drive_lines=True,
            use_mw_fem=True,
            shared_drive_line=True,
        )
        return connectivity

    @pytest.fixture
    def instruments(self):
        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1])
        instruments.add_lf_fem(controller=1, slots=[2, 3])
        return instruments

    def test_two_stage_dot_then_qubit(self, instruments, temp_dir):
        """Stage 1 builds dots, Stage 2 adds qubits with drive lines."""
        qubit_pair_sensor_map = {"q1_q2": ["sensor_1"], "q2_q3": ["sensor_2"]}

        # Stage 1: dot layer only
        connectivity_s1 = self._make_stage1_connectivity(
            self.GLOBAL_GATES, self.SENSOR_DOTS, self.QUANTUM_DOTS, self.QUANTUM_DOT_PAIRS
        )
        allocate_wiring(connectivity_s1, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity_s1, "127.0.0.1", "test_cluster", machine, path=temp_dir
        )
        machine = build_base_quam(
            machine, calibration_db_path=temp_dir, connect_qdac=False, save=False
        )

        assert len(machine.quantum_dots) == 3
        assert len(machine.sensor_dots) == 2
        assert not hasattr(machine, "qubits") or len(getattr(machine, "qubits", {})) == 0

        # Stage 2: add qubits with drive lines
        instruments_s2 = Instruments()
        instruments_s2.add_mw_fem(controller=1, slots=[1])
        instruments_s2.add_lf_fem(controller=1, slots=[2, 3])

        connectivity_s2 = self._make_stage2_connectivity(
            self.GLOBAL_GATES, self.SENSOR_DOTS, self.QUANTUM_DOTS, self.QUANTUM_DOT_PAIRS
        )
        allocate_wiring(connectivity_s2, instruments_s2)

        machine = build_quam_wiring(
            connectivity_s2, "127.0.0.1", "test_cluster", machine, path=temp_dir
        )
        machine = build_loss_divincenzo_quam(
            machine,
            qubit_pair_sensor_map=qubit_pair_sensor_map,
            implicit_mapping=True,
            save=False,
        )

        assert len(machine.quantum_dots) == 3
        assert len(machine.sensor_dots) == 2
        assert len(machine.qubits) == 3
        assert len(machine.quantum_dot_pairs) == 2

        for qubit in machine.qubits.values():
            assert getattr(qubit, "xy_channel", None) is not None

    def test_incremental_drive_lines(self, temp_dir):
        """Stage 1 with shared instruments, Stage 2 adds only drive lines."""
        qubit_pair_sensor_map = {"q1_q2": ["sensor_1"]}

        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1])
        instruments.add_lf_fem(controller=1, slots=[2, 3])

        # Stage 1
        connectivity_s1 = self._make_stage1_connectivity(
            self.GLOBAL_GATES, self.SENSOR_DOTS, self.QUANTUM_DOTS, self.QUANTUM_DOT_PAIRS
        )
        allocate_wiring(connectivity_s1, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity_s1, "127.0.0.1", "test_cluster", machine, path=temp_dir
        )
        machine = build_base_quam(
            machine, calibration_db_path=temp_dir, connect_qdac=False, save=False
        )

        # Stage 2: only drive lines
        connectivity_drive = Connectivity()
        connectivity_drive.add_quantum_dot_drive_lines(
            quantum_dots=self.QUANTUM_DOTS, use_mw_fem=True, shared_line=True
        )
        allocate_wiring(connectivity_drive, instruments)

        machine = build_quam_wiring(
            connectivity_drive, "127.0.0.1", "test_cluster", machine, path=temp_dir
        )
        machine = build_loss_divincenzo_quam(
            machine,
            qubit_pair_sensor_map=qubit_pair_sensor_map,
            implicit_mapping=True,
            save=False,
        )

        assert len(machine.qubits) == 3
        for qubit in machine.qubits.values():
            assert getattr(qubit, "xy_channel", None) is not None


class TestQuantumDotsBaseQuamOnly:
    """Stage 1 only: verify BaseQuamQD without qubit registration."""

    def test_dots_without_drive_lines(self, temp_dir):
        """Build a dot-only system with no drive lines or qubits."""
        instruments = Instruments()
        instruments.add_lf_fem(controller=1, slots=[1, 2])

        connectivity = Connectivity()
        connectivity.add_voltage_gate_lines(voltage_gates=[1], name="rb")
        connectivity.add_sensor_dots(sensor_dots=[1], shared_resonator_line=False, use_mw_fem=False)
        connectivity.add_quantum_dots(quantum_dots=[1, 2, 3], add_drive_lines=False)
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2), (2, 3)])
        allocate_wiring(connectivity, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir
        )
        machine = build_base_quam(
            machine, calibration_db_path=temp_dir, connect_qdac=False, save=False
        )

        assert len(machine.quantum_dots) == 3
        assert len(machine.sensor_dots) == 1
        assert len(machine.virtual_gate_sets) > 0
        vgs = machine.virtual_gate_sets["main_qpu"]
        assert len(vgs.channels) >= 3


class TestQuantumDotsLargeSystem:
    """Larger quantum dot systems to stress-test the wiring allocation."""

    def test_eight_dots_four_sensors(self, temp_dir):
        """8 quantum dots, 4 sensor dots, 7 pairs — larger-scale system."""
        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1, 2])
        instruments.add_lf_fem(controller=1, slots=[3, 4, 5, 6])

        quantum_dots = list(range(1, 9))
        sensor_dots = [1, 2, 3, 4]
        dot_pairs = [(i, i + 1) for i in range(1, 8)]

        connectivity = Connectivity()
        connectivity.add_sensor_dots(
            sensor_dots=sensor_dots, shared_resonator_line=False, use_mw_fem=False
        )
        connectivity.add_quantum_dots(
            quantum_dots=quantum_dots,
            add_drive_lines=True,
            use_mw_fem=True,
            shared_drive_line=True,
        )
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=dot_pairs)
        allocate_wiring(connectivity, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity, "127.0.0.1", "test_cluster", machine, path=temp_dir
        )
        machine = build_quam_qd(
            machine,
            calibration_db_path=temp_dir,
            connect_qdac=False,
            save=False,
        )

        assert len(machine.quantum_dots) == 8
        assert len(machine.sensor_dots) == 4
        assert len(machine.qubits) == 8
        assert len(machine.quantum_dot_pairs) == 7
