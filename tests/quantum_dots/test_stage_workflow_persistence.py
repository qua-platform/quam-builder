"""Tests for persistence of calibration data across two-stage wiring."""

from pathlib import Path

import pytest

from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots import build_base_quam, build_loss_divincenzo_quam


EXAMPLE_GLOBAL_GATES = [1]
EXAMPLE_SENSOR_DOTS = [1, 2]
EXAMPLE_QUANTUM_DOTS = [1, 2, 3]
EXAMPLE_QUANTUM_DOT_PAIRS = [(1, 2), (2, 3)]


def _make_stage1_connectivity():
    connectivity = Connectivity()
    if EXAMPLE_GLOBAL_GATES:
        connectivity.add_voltage_gate_lines(voltage_gates=EXAMPLE_GLOBAL_GATES, name="rb")
    connectivity.add_sensor_dots(
        sensor_dots=EXAMPLE_SENSOR_DOTS,
        shared_resonator_line=False,
        use_mw_fem=False,
    )
    connectivity.add_quantum_dots(
        quantum_dots=EXAMPLE_QUANTUM_DOTS,
        add_drive_lines=False,
    )
    connectivity.add_quantum_dot_pairs(quantum_dot_pairs=EXAMPLE_QUANTUM_DOT_PAIRS)
    return connectivity


def _make_stage2_connectivity():
    connectivity = Connectivity()
    if EXAMPLE_GLOBAL_GATES:
        connectivity.add_voltage_gate_lines(voltage_gates=EXAMPLE_GLOBAL_GATES, name="rb")
    connectivity.add_sensor_dots(
        sensor_dots=EXAMPLE_SENSOR_DOTS,
        shared_resonator_line=False,
        use_mw_fem=False,
    )
    connectivity.add_quantum_dot_pairs(quantum_dot_pairs=EXAMPLE_QUANTUM_DOT_PAIRS)
    connectivity.add_quantum_dots(
        quantum_dots=EXAMPLE_QUANTUM_DOTS,
        add_drive_lines=True,
        use_mw_fem=True,
        shared_drive_line=True,
    )
    return connectivity


def _make_instruments():
    instruments = Instruments()
    instruments.add_mw_fem(controller=1, slots=[1])
    instruments.add_lf_fem(controller=1, slots=[2, 3])
    return instruments


def _add_calibration_data(machine: BaseQuamQD) -> None:
    gate_set = machine.virtual_gate_sets["main_qpu"]
    virtual_targets = [
        name for name in gate_set.layers[0].source_gates if name.startswith("virtual_dot_")
    ][:2]
    gate_set.add_to_layer(
        layer_id="calibration_layer",
        source_gates=["virtual_calibration_axis"],
        target_gates=virtual_targets,
        matrix=[[1.0, -1.0]],
    )

    quantum_dot = machine.quantum_dots["virtual_dot_1"]
    quantum_dot.with_step_point(
        "calibration_idle",
        {"virtual_dot_1": 0.12},
        hold_duration=120,
    ).with_sequence("calibration_sequence", ["calibration_idle"])


def test_calibration_data_persists_across_two_stage_build(tmp_path):
    """Ensure virtual gates, points, and macros survive stage 2 wiring/build."""
    stage1_dir = Path(tmp_path) / "stage1"
    stage2_dir = Path(tmp_path) / "stage2"

    connectivity_stage1 = _make_stage1_connectivity()
    instruments_stage1 = _make_instruments()
    allocate_wiring(connectivity_stage1, instruments_stage1)

    machine_stage1 = BaseQuamQD()
    machine_stage1 = build_quam_wiring(
        connectivity_stage1,
        host_ip="127.0.0.1",
        cluster_name="test_cluster",
        quam_instance=machine_stage1,
        path=stage1_dir,
    )
    machine_stage1 = build_base_quam(
        machine_stage1,
        calibration_db_path=stage1_dir,
        connect_qdac=False,
        save=False,
    )

    _add_calibration_data(machine_stage1)
    machine_stage1.save(stage1_dir)

    machine_loaded = BaseQuamQD.load(stage1_dir)
    connectivity_stage2 = _make_stage2_connectivity()
    instruments_stage2 = _make_instruments()
    allocate_wiring(connectivity_stage2, instruments_stage2)

    machine_stage2 = build_quam_wiring(
        connectivity_stage2,
        host_ip="127.0.0.1",
        cluster_name="test_cluster",
        quam_instance=machine_loaded,
        path=stage2_dir,
    )
    machine_stage2 = build_loss_divincenzo_quam(
        machine_stage2,
        qubit_pair_sensor_map={"q1_q2": ["sensor_1"]},
        implicit_mapping=True,
        save=False,
    )

    gate_set = machine_stage2.virtual_gate_sets["main_qpu"]
    calibration_layer = next(
        layer for layer in gate_set.layers if layer.id == "calibration_layer"
    )
    assert calibration_layer.source_gates == ["virtual_calibration_axis"]

    quantum_dot = machine_stage2.quantum_dots["virtual_dot_1"]
    assert "calibration_idle" in quantum_dot.macros
    assert "calibration_sequence" in quantum_dot.macros

    point_name = f"{quantum_dot.id}_calibration_idle"
    assert point_name in gate_set.macros
