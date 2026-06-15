"""Shared machine builder for the macro customization tutorial.

Builds a LossDiVincenzoQuam using the combined wiring workflow
(Connectivity -> Instruments -> allocate_wiring -> build_quam_wiring ->
build_quam).  Adds voltage step points so default state macros can run.

The machine comes pre-wired with default macros and pulses (via build_quam).
The tutorial notebook re-calls wire_machine_macros with custom catalogs and
overrides to demonstrate the macro customization API.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, Optional, Union

from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring

from quam_builder.architecture.quantum_dots.operations.names import VoltagePointName
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, LossDiVincenzoQuam
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots import build_quam


def build_tutorial_machine(
    *,
    mw_fem_slots: Optional[list[int]] = None,
    lf_fem_slots: Optional[list[int]] = None,
    cluster_config_path: Optional[Union[Path, str]] = None,
) -> LossDiVincenzoQuam:
    """Build a minimal machine using the combined wiring workflow.

    Uses Connectivity + Instruments + allocate_wiring to define the
    hardware layout, then build_quam to construct the full
    LossDiVincenzoQuam in a single stage.

    Args:
        mw_fem_slots: MW FEM slot indices (OPX+), default ``[1]``.
        lf_fem_slots: LF FEM slot indices, default ``[2]`` (single module).
        cluster_config_path: If set, read ``host`` and ``cluster_name`` for
            :func:`build_quam_wiring` from this JSON (e.g. ``.qm_cluster_config.json``).
            Otherwise use ``127.0.0.1`` and ``"tutorial"``.

    Returns a machine with:

    - 2 quantum dots (virtual_dot_1, virtual_dot_2)
    - 1 quantum dot pair (virtual_dot_1_virtual_dot_2_pair)
    - 1 sensor dot (virtual_sensor_1)
    - 2 qubits (q1, q2) with shared MW drive line
    - 1 qubit pair (q1_q2)
    - Voltage step points (initialize, measure, empty) for state macros
    - Default macros and pulses (wired by build_quam)
    """
    mw = mw_fem_slots if mw_fem_slots is not None else [1]
    lf = lf_fem_slots if lf_fem_slots is not None else [2]
    host, cluster = "127.0.0.1", "tutorial"
    if cluster_config_path is not None:
        cfg_path = Path(cluster_config_path)
        if cfg_path.is_file():
            with open(cfg_path, encoding="utf-8") as f:
                cluster_json = json.load(f)
            host = cluster_json.get("host", host)
            cluster = cluster_json.get("cluster_name", cluster)

    connectivity = Connectivity()
    connectivity.add_sensor_dots(sensor_dots=[1], shared_resonator_line=False)
    connectivity.add_quantum_dots(quantum_dots=[1, 2])
    connectivity.add_quantum_dot_drive_lines(
        quantum_dots=[1, 2], shared_line=True, use_mw_fem=True
    )
    connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2)])

    instruments = Instruments()
    instruments.add_mw_fem(controller=1, slots=mw)
    instruments.add_lf_fem(controller=1, slots=lf)

    allocate_wiring(connectivity, instruments)

    with tempfile.TemporaryDirectory() as tmp:
        machine = build_quam_wiring(
            connectivity,
            host,
            cluster,
            BaseQuamQD(),
            path=tmp,
        )
        machine = build_quam(
            machine,
            calibration_db_path=tmp,
            qubit_pair_sensor_map={"q1_q2": ["sensor_1"]},
            save=False,
        )

    machine.reset_voltage_sequence("main_qpu")
    _add_tutorial_state_points(machine)
    return machine


def _add_tutorial_state_points(machine: LossDiVincenzoQuam) -> None:
    """Add voltage step points so default state macros can run."""
    for qubit in machine.qubits.values():
        dot_id = qubit.quantum_dot.id
        qubit.add_point(VoltagePointName.INITIALIZE, {dot_id: 0.10}, duration=200)
        qubit.add_point(VoltagePointName.MEASURE, {dot_id: 0.15}, duration=200)
        qubit.add_point(VoltagePointName.EMPTY, {dot_id: 0.00}, duration=200)

    for pair in machine.quantum_dot_pairs.values():
        dot_ids = [qd.id for qd in pair.quantum_dots]
        v_init: Dict[str, float] = {d: 0.10 for d in dot_ids}
        v_meas: Dict[str, float] = {d: 0.15 for d in dot_ids}
        v_empty: Dict[str, float] = {d: 0.00 for d in dot_ids}
        pair.add_point(VoltagePointName.INITIALIZE, v_init, duration=200)
        pair.add_point(VoltagePointName.MEASURE, v_meas, duration=200)
        pair.add_point(VoltagePointName.EMPTY, v_empty, duration=200)
