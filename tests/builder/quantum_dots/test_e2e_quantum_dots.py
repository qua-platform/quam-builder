"""End-to-end tests for quantum dots QUAM construction using the wiring tools.

Tests the full workflow from instrument definition → connectivity setup →
wiring allocation → QUAM construction for quantum dot architectures
(combined, two-stage, incremental drive-line workflows).

These tests exercise the interoperability with py-qua-tools (qualang-tools)
wiring infrastructure.
"""

# pylint: disable=no-member

import inspect
import shutil
import tempfile

import pytest
from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring
from qualang_tools.wirer.connectivity.wiring_spec import WiringFrequency

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


def _quantum_dot_drive_line_kw_dc():
    """LF-FEM drives: ``wiring_frequency=DC`` (new API) or ``use_mw_fem=False`` (current)."""
    params = inspect.signature(Connectivity.add_quantum_dot_drive_lines).parameters
    if "wiring_frequency" in params:
        return {"wiring_frequency": WiringFrequency.DC}
    return {"use_mw_fem": False}


def _quantum_dot_drive_line_kw_rf():
    """MW-FEM drives: ``wiring_frequency=RF`` (new API) or ``use_mw_fem=True`` (current)."""
    params = inspect.signature(Connectivity.add_quantum_dot_drive_lines).parameters
    if "wiring_frequency" in params:
        return {"wiring_frequency": WiringFrequency.RF}
    return {"use_mw_fem": True}


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
        connectivity.add_sensor_dots(sensor_dots=sensor_dots, shared_resonator_line=False)
        connectivity.add_quantum_dots(quantum_dots=quantum_dots)
        connectivity.add_quantum_dot_drive_lines(quantum_dots=quantum_dots, shared_line=True)
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
        connectivity.add_sensor_dots(sensor_dots=[1], shared_resonator_line=False)
        connectivity.add_quantum_dots(quantum_dots=[1, 2])
        connectivity.add_quantum_dot_drive_lines(quantum_dots=[1, 2], shared_line=True)
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
        connectivity.add_sensor_dots(sensor_dots=sensor_dots, shared_resonator_line=False)
        connectivity.add_quantum_dots(quantum_dots=quantum_dots)
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=dot_pairs)
        return connectivity

    @staticmethod
    def _make_stage2_connectivity(global_gates, sensor_dots, quantum_dots, dot_pairs):
        connectivity = Connectivity()
        connectivity.add_voltage_gate_lines(voltage_gates=global_gates, name="rb")
        connectivity.add_sensor_dots(sensor_dots=sensor_dots, shared_resonator_line=False)
        connectivity.add_quantum_dot_pairs(quantum_dot_pairs=dot_pairs)
        connectivity.add_quantum_dots(quantum_dots=quantum_dots)
        connectivity.add_quantum_dot_drive_lines(quantum_dots=quantum_dots, shared_line=True)
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
            assert getattr(qubit, "xy", None) is not None

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
            quantum_dots=self.QUANTUM_DOTS, shared_line=True
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
            assert getattr(qubit, "xy", None) is not None


class TestQuantumDotsBaseQuamOnly:
    """Stage 1 only: verify BaseQuamQD without qubit registration."""

    def test_dots_without_drive_lines(self, temp_dir):
        """Build a dot-only system with no drive lines or qubits."""
        instruments = Instruments()
        instruments.add_lf_fem(controller=1, slots=[1, 2])

        connectivity = Connectivity()
        connectivity.add_voltage_gate_lines(voltage_gates=[1], name="rb")
        connectivity.add_sensor_dots(sensor_dots=[1], shared_resonator_line=False)
        connectivity.add_quantum_dots(quantum_dots=[1, 2, 3])
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
        connectivity.add_sensor_dots(sensor_dots=sensor_dots, shared_resonator_line=False)
        connectivity.add_quantum_dots(quantum_dots=quantum_dots)
        connectivity.add_quantum_dot_drive_lines(quantum_dots=quantum_dots, shared_line=True)
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


class TestLfFemSingleDriveWorkflow:
    """E2E tests for LF-FEM-only systems using LF-FEM drive wiring.

    When no MW-FEM is present and drive lines use ``WiringFrequency.DC``, the
    wirer allocates single LF-FEM outputs for drive lines. quam-builder should
    create XYDriveSingle (not XYDriveMW) for these.
    """

    @pytest.fixture
    def instruments(self):
        instruments = Instruments()
        instruments.add_lf_fem(controller=1, slots=[3, 5])
        return instruments

    def _run_lf_only_two_stage(self, instruments, temp_dir):
        """Two-stage build with LF-FEM only and DC (LF-FEM) drive lines."""
        sensor_dots = [1, 2]
        quantum_dots = [1, 2, 3, 4]
        dot_pairs = [(1, 2), (3, 4)]
        qubit_pair_sensor_map = {"q1_q2": ["sensor_1"], "q3_q4": ["sensor_2"]}

        # Stage 1
        conn_s1 = Connectivity()
        conn_s1.add_sensor_dots(sensor_dots=sensor_dots, shared_resonator_line=False)
        conn_s1.add_quantum_dots(quantum_dots=quantum_dots)
        conn_s1.add_quantum_dot_pairs(quantum_dot_pairs=dot_pairs)
        allocate_wiring(conn_s1, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(conn_s1, "127.0.0.1", "test_cluster", machine, path=temp_dir)
        machine = build_base_quam(
            machine, calibration_db_path=temp_dir, connect_qdac=False, save=False
        )

        # Stage 2 with LF-FEM-only instruments (LF-FEM drive lines via WiringFrequency.DC)
        instruments_s2 = Instruments()
        instruments_s2.add_lf_fem(controller=1, slots=[3, 5])

        conn_s2 = Connectivity()
        conn_s2.add_sensor_dots(sensor_dots=sensor_dots, shared_resonator_line=False)
        conn_s2.add_quantum_dots(quantum_dots=quantum_dots)
        conn_s2.add_quantum_dot_drive_lines(
            quantum_dots=quantum_dots,
            shared_line=True,
            **_quantum_dot_drive_line_kw_dc(),
        )
        conn_s2.add_quantum_dot_pairs(quantum_dot_pairs=dot_pairs)
        allocate_wiring(conn_s2, instruments_s2)

        machine = build_quam_wiring(conn_s2, "127.0.0.1", "test_cluster", machine, path=temp_dir)
        machine = build_loss_divincenzo_quam(
            machine,
            qubit_pair_sensor_map=qubit_pair_sensor_map,
            implicit_mapping=True,
            save=False,
        )
        return machine

    def test_lf_fem_drives_are_xy_drive_single(self, instruments, temp_dir):
        """With LF-FEM (DC) drive wiring, all XY drives should be XYDriveSingle."""
        from quam_builder.architecture.quantum_dots.components.xy_drive import (
            XYDriveSingle,
        )

        machine = self._run_lf_only_two_stage(instruments, temp_dir)

        assert len(machine.qubits) == 4
        for qubit_id, qubit in machine.qubits.items():
            assert (
                getattr(qubit, "xy", None) is not None
            ), f"Qubit {qubit_id} should have an XY drive"
            assert isinstance(qubit.xy, XYDriveSingle), (
                f"Qubit {qubit_id} XY drive should be XYDriveSingle, "
                f"got {type(qubit.xy).__name__}"
            )

    def test_lf_fem_drive_port_refs_are_analog(self, instruments, temp_dir):
        """XY drive port references should point at analog_outputs, not mw_outputs."""
        machine = self._run_lf_only_two_stage(instruments, temp_dir)

        for qubit_id in machine.qubits:
            wiring_xy = machine.wiring["qubits"][qubit_id].get("xy", {})
            raw_ref = wiring_xy.get_raw_value("opx_output")
            ref = str(raw_ref)
            assert "analog_outputs" in ref, (
                f"Qubit {qubit_id} drive wiring should reference analog_outputs, " f"got: {ref}"
            )
            assert "mw_outputs" not in ref


class TestTwoStageWiringIntegration:
    """E2E tests verifying the four wiring behaviours added to the two-stage pipeline."""

    GLOBAL_GATES = [1]
    SENSOR_DOTS = [1, 2]
    QUANTUM_DOTS = [1, 2, 3]
    QUANTUM_DOT_PAIRS = [(1, 2), (2, 3)]
    QUBIT_PAIR_SENSOR_MAP = {"q1_q2": ["sensor_1"], "q2_q3": ["sensor_2"]}

    @pytest.fixture
    def instruments(self):
        instruments = Instruments()
        instruments.add_mw_fem(controller=1, slots=[1])
        instruments.add_lf_fem(controller=1, slots=[2, 3])
        return instruments

    def _run_two_stage(self, instruments, temp_dir):
        """Run the full two-stage workflow and return the final machine."""
        # Stage 1: dot layer only (no drive lines)
        connectivity_s1 = Connectivity()
        connectivity_s1.add_voltage_gate_lines(voltage_gates=self.GLOBAL_GATES, name="rb")
        connectivity_s1.add_sensor_dots(sensor_dots=self.SENSOR_DOTS, shared_resonator_line=False)
        connectivity_s1.add_quantum_dots(quantum_dots=self.QUANTUM_DOTS)
        connectivity_s1.add_quantum_dot_pairs(quantum_dot_pairs=self.QUANTUM_DOT_PAIRS)
        allocate_wiring(connectivity_s1, instruments)

        machine = BaseQuamQD()
        machine = build_quam_wiring(
            connectivity_s1, "127.0.0.1", "test_cluster", machine, path=temp_dir
        )
        machine = build_base_quam(
            machine, calibration_db_path=temp_dir, connect_qdac=False, save=False
        )

        # Stage 2: add qubits with drive lines
        instruments_s2 = Instruments()
        instruments_s2.add_mw_fem(controller=1, slots=[1])
        instruments_s2.add_lf_fem(controller=1, slots=[2, 3])

        connectivity_s2 = Connectivity()
        connectivity_s2.add_voltage_gate_lines(voltage_gates=self.GLOBAL_GATES, name="rb")
        connectivity_s2.add_sensor_dots(sensor_dots=self.SENSOR_DOTS, shared_resonator_line=False)
        connectivity_s2.add_quantum_dot_pairs(quantum_dot_pairs=self.QUANTUM_DOT_PAIRS)
        connectivity_s2.add_quantum_dots(quantum_dots=self.QUANTUM_DOTS)
        connectivity_s2.add_quantum_dot_drive_lines(
            quantum_dots=self.QUANTUM_DOTS,
            shared_line=True,
            **_quantum_dot_drive_line_kw_rf(),
        )
        allocate_wiring(connectivity_s2, instruments_s2)

        machine = build_quam_wiring(
            connectivity_s2, "127.0.0.1", "test_cluster", machine, path=temp_dir
        )
        machine = build_loss_divincenzo_quam(
            machine,
            qubit_pair_sensor_map=self.QUBIT_PAIR_SENSOR_MAP,
            implicit_mapping=True,
            save=False,
        )
        return machine

    def test_two_stage_ports_materialized(self, instruments, temp_dir):
        """All wiring port references should have corresponding port objects."""
        machine = self._run_two_stage(instruments, temp_dir)

        def _collect_port_refs(obj, refs=None):
            if refs is None:
                refs = set()
            if isinstance(obj, dict):
                for v in obj.values():
                    _collect_port_refs(v, refs)
            elif isinstance(obj, str) and obj.startswith("#/ports/"):
                refs.add(obj)
            return refs

        wiring_refs = _collect_port_refs(machine.wiring)
        for ref in wiring_refs:
            parts = ref.lstrip("#/").split("/")
            node = machine
            for part in parts:
                if isinstance(node, dict):
                    assert part in node, f"Port reference {ref} not materialized"
                    node = node[part]
                else:
                    assert hasattr(node, part), f"Port reference {ref} not materialized"
                    node = getattr(node, part)

    def test_two_stage_sensor_dots_wired_to_pairs(self, instruments, temp_dir):
        """Each quantum dot pair should have sensor dots populated per the map."""
        machine = self._run_two_stage(instruments, temp_dir)

        pair_q1_q2 = machine.qubit_pairs["q1_q2"]
        assert len(pair_q1_q2.quantum_dot_pair.sensor_dots) > 0
        assert "#/sensor_dots/virtual_sensor_1" in pair_q1_q2.quantum_dot_pair.sensor_dots

        pair_q2_q3 = machine.qubit_pairs["q2_q3"]
        assert len(pair_q2_q3.quantum_dot_pair.sensor_dots) > 0
        assert "#/sensor_dots/virtual_sensor_2" in pair_q2_q3.quantum_dot_pair.sensor_dots

    def test_two_stage_preferred_readout_dot(self, instruments, temp_dir):
        """Each qubit should have preferred_readout_quantum_dot set.

        When a qubit belongs to multiple pairs, the last pair processed
        wins (same last-write-wins semantics as the original quam_factory).
        We verify the exact expected values for this 3-dot, 2-pair topology:
        pairs processed in order q1_q2 then q2_q3.
        """
        machine = self._run_two_stage(instruments, temp_dir)

        assert machine.qubits["q1"].preferred_readout_quantum_dot == "virtual_dot_2"
        assert machine.qubits["q2"].preferred_readout_quantum_dot == "virtual_dot_3"
        assert machine.qubits["q3"].preferred_readout_quantum_dot == "virtual_dot_2"

    def test_two_stage_resonator_not_sticky(self, instruments, temp_dir):
        """Readout resonators should not have sticky enabled after two-stage build."""
        machine = self._run_two_stage(instruments, temp_dir)

        for sensor in machine.sensor_dots.values():
            rr = sensor.readout_resonator
            assert rr.sticky is None, f"Readout resonator {rr.id} should not have sticky"
