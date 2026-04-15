"""Shared machine builder for the macro customization tutorial.

Builds a LossDiVincenzoQuam using the combined wiring workflow
(Connectivity -> Instruments -> allocate_wiring -> build_quam_wiring ->
build_quam).  Adds voltage step points so default state macros can run.

The machine comes pre-wired with default macros and pulses (via build_quam).
The tutorial notebook re-calls wire_machine_macros with custom catalogs and
overrides to demonstrate the macro customization API.
"""

from __future__ import annotations

import tempfile
from typing import Dict

from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring

from quam_builder.architecture.quantum_dots.operations.names import VoltagePointName
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, LossDiVincenzoQuam
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots import build_quam


def build_tutorial_machine() -> LossDiVincenzoQuam:
    """Build a minimal machine using the combined wiring workflow.

    Uses Connectivity + Instruments + allocate_wiring to define the
    hardware layout, then build_quam to construct the full
    LossDiVincenzoQuam in a single stage.

    Returns a machine with:

    - 2 quantum dots (virtual_dot_1, virtual_dot_2)
    - 1 quantum dot pair (virtual_dot_1_virtual_dot_2_pair)
    - 1 sensor dot (virtual_sensor_1)
    - 2 qubits (q1, q2) with shared MW drive line
    - 1 qubit pair (q1_q2)
    - Voltage step points (initialize, measure, empty) for state macros
    - Default macros and pulses (wired by build_quam)
    """
    connectivity = Connectivity()
    connectivity.add_sensor_dots(sensor_dots=[1], shared_resonator_line=False)
    connectivity.add_quantum_dots(quantum_dots=[1, 2])
    connectivity.add_quantum_dot_drive_lines(quantum_dots=[1, 2], shared_line=True, use_mw_fem=True)
    connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2)])

    instruments = Instruments()
    instruments.add_mw_fem(controller=1, slots=[1])
    instruments.add_lf_fem(controller=1, slots=[2])

    allocate_wiring(connectivity, instruments)

    with tempfile.TemporaryDirectory() as tmp:
        machine = build_quam_wiring(
            connectivity,
            "127.0.0.1",
            "tutorial",
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
