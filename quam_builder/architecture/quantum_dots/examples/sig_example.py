"""
Builds a LossDiVincenzoQuam using the combined wiring workflow
(Connectivity -> Instruments -> allocate_wiring -> build_quam_wiring ->
build_quam).  Adds voltage step points so default state macros can run.

The machine comes pre-wired with default macros and pulses (via build_quam).
The tutorial notebook re-calls wire_machine_macros with custom catalogs and
overrides to demonstrate the macro customization API.

Default parameters
------------------
All architecture defaults (pulse lengths, amplitudes, frequencies, macro
timing, etc.) are defined in ``quam_builder.architecture.quantum_dots.defaults``.

"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import numpy as np
from typing import List

from qualang_tools.wirer import (
    Connectivity,
    Instruments,
    allocate_wiring,
    visualize,
)  # noqa: E402

from quam_builder.architecture.quantum_dots.operations.macro_catalog import (  # noqa: E402
    VoltageBalancedMacroCatalog,
)
from quam_builder.architecture.quantum_dots.operations.names import (  # noqa: E402
    DrivePulseName,
    SingleQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.qpu import (
    BaseQuamQD,
    LossDiVincenzoQuam,
)  # noqa: E402
from quam_builder.builder.qop_connectivity import build_quam_wiring  # noqa: E402
from quam_builder.builder.quantum_dots import build_quam  # noqa: E402


def build_machine(path: None | Path = None) -> LossDiVincenzoQuam:
    """Build a machine using the combined wiring workflow.

    Uses Connectivity + Instruments + allocate_wiring to define the
    hardware layout, then build_quam to construct the full
    LossDiVincenzoQuam in a single stage.

    Returns a machine with:

    - 4 quantum dots (virtual_dot_1, virtual_dot_2)
    - 3 quantum dot pair (virtual_dot_1_virtual_dot_2_pair)
    - 2 sensor dot (virtual_sensor_1)
    - 4 qubits (q1, q2) with shared MW drive line
    - 3 qubit pair (q1_q2)
    - Voltage step points (initialize, measure, empty) for state macros
    - Voltage Balanced macros and pulses (wired by build_quam)
    """
    connectivity = Connectivity()

    # Create dummy sensor_dot elements?
    connectivity.add_sensor_dots(sensor_dots=[1, 2], shared_resonator_line=False)
    connectivity.add_quantum_dots(quantum_dots=[1, 2, 3, 4])
    connectivity.add_quantum_dot_drive_lines(
        quantum_dots=[1, 2, 3, 4], shared_line=True, use_mw_fem=True
    )
    # Add second drive line to the connectivity
    connectivity.add_quantum_dot_drive_lines(
        quantum_dots=[1, 2, 3, 4], shared_line=True, use_mw_fem=True
    )
    connectivity.add_quantum_dot_pairs(quantum_dot_pairs=[(1, 2), (2, 3), (3, 4)])

    # connectivity.add_voltage_gate_lines(
    #     voltage_gates=[1, 2], name="rb"
    # )  # right, middle and left barriers to reservoirs

    instruments = Instruments()
    instruments.add_mw_fem(controller=1, slots=[1])
    instruments.add_lf_fem(controller=1, slots=[5, 6])

    allocate_wiring(connectivity, instruments)

    config_path = Path(__file__).resolve().parents[4] / ".qm_cluster_config.json.example"
    with open(config_path, encoding="utf-8") as f:
        cluster_config = json.load(f)
    host = cluster_config["host"]
    cluster_name = cluster_config["cluster_name"]

    print("Allocating wiring...")
    if path is None:
        path = Path(__file__).resolve().parent / "quam_state"

    machine = build_quam_wiring(
        connectivity,
        host,
        cluster_name,
        BaseQuamQD(),
        path=path,
    )

    machine = build_quam(
        machine,
        qubit_pair_sensor_map={
            "q1_q2": ["sensor_1"],
            "q2_q3": ["sensor_1"],
            "q3_q4": ["sensor_2"],
        },
        catalogs=[VoltageBalancedMacroCatalog()],
        save=True,
        path=path,
    )

    # Optional: Visualize Wiring
    # Uncomment to visualize wiring (requires a GUI backend)
    import matplotlib

    # matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt  # noqa: E402

    visualize(
        connectivity.elements,
        available_channels=instruments.available_channels,
        use_matplotlib=True,
    )
    plt.show()

    return machine


def populate_machine(machine: LossDiVincenzoQuam):

    #######################################
    ###### Qubits Physical Properties #####
    #######################################

    # XY / MW-FEM: QuAM uses IF = larmor_frequency - MW_upconverter (see XYDriveMW).
    # QM enforces |IF| <= 500 MHz. The old name ``LO`` here was really the *Larmor*
    # centre (~9.7 GHz), not the FEM LO; leaving upconverter at ~5 GHz made IF ~4.7 GHz.
    larmor_center_hz = 18e9
    mw_upconverter_hz = larmor_center_hz
    qubit_frequencies = [
        larmor_center_hz - 15e6,
        larmor_center_hz - 5e6,
        larmor_center_hz + 5e6,
        larmor_center_hz + 15e6,
    ]

    for i, q in enumerate(machine.qubits.values()):
        q.xy.opx_output.band = 3
        # Same params for each qubit for now. Subject to change.
        q.macros[VoltagePointName.INITIALIZE].update(ramp_duration=2000, hold_duration=200)
        q.macros[VoltagePointName.MEASURE].update(buffer_duration=240)
        q.macros[VoltagePointName.EMPTY].update(hold_duration=80)

        # MW FEM LO on this XY line (shared port → same value each iteration is fine).
        q.xy.opx_output.upconverter_frequency = mw_upconverter_hz

        # Absolute drive / Larmor frequency (RF), not the OPX IF.
        q_xy = q.macros[SingleQubitMacroName.XY_DRIVE]
        q_xy.update(frequency=qubit_frequencies[i])

        q.xy.operations[f"{DrivePulseName.GAUSSIAN}_x90"].amplitude = 0.17

        # Default values
        q.T1 = 1e-6
        q.T2ramsey = 0.5e-6
        q.T2echo = 2e-6

    #########################
    ###### State Points #####
    #########################

    for i, qdp in enumerate(machine.quantum_dot_pairs.values()):
        qdp.add_point(
            point_name=VoltagePointName.INITIALIZE,
            voltages={d.id: (i + 1) * 0.015 for d in qdp.quantum_dots},
            duration=1000,
        )
        qdp.add_point(
            point_name=VoltagePointName.EMPTY,
            voltages={d.id: (i + 1) * 0.02 for d in qdp.quantum_dots},
            duration=1500,
        )
        qdp.add_point(
            point_name=VoltagePointName.MEASURE,
            voltages={d.id: (i + 1) * 0.025 for d in qdp.quantum_dots},
            duration=1000,
        )

    ##############################
    ###### Sensor Properties #####
    ##############################

    resonator_frequencies = [100, 100]
    for i, s in enumerate(machine.sensor_dots.values()):
        s.readout_resonator.intermediate_frequency = resonator_frequencies[i]
        s.readout_resonator.operations["readout"].amplitude = 0.02
        s.readout_resonator.operations["readout"].length = 50_000  # 50us

    ################################
    ###### Compensation Matrix #####
    ################################

    full_given_matrix = np.array(
        [
            [1.49696, 0.5218, 0.36891, 1.0, -0.15019, 0.11477, 0.02468],
            [-0.54456, 0.4782, 0.33809, 1.0, 0.01011, 0.04221, 0.09137],
            [-0.55239, -0.58, 0.58994, 1.0, 0.08125, -0.14962, 0.02272],
            [-0.40001, -0.42, -1.29694, 1.0, 0.05883, -0.00736, -0.13877],
            [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ]
    )

    inverse_matrix = np.linalg.inv(full_given_matrix)
    barrier_orthogonalising_submatrix = -full_given_matrix[:4, 4:]

    gate_set_id = next(iter(machine.virtual_gate_sets))
    vgs = machine.virtual_gate_sets[gate_set_id]
    qds = machine.quantum_dots

    # Orthogonalise the barriers. Detuning will be another layer.
    machine.update_cross_compensation_submatrix(
        virtual_names=["virtual_barrier_1", "virtual_barrier_2", "virtual_barrier_3"],
        channels=[
            qds["virtual_dot_1"].physical_channel,
            qds["virtual_dot_2"].physical_channel,
            qds["virtual_dot_3"].physical_channel,
            qds["virtual_dot_4"].physical_channel,
        ],
        matrix=barrier_orthogonalising_submatrix,
        target="opx",
    )

    #################################
    ###### Define Detuning Axis #####
    #################################

    update_detuning_axis(machine, inverse_matrix)

    vgs.add_to_layer(
        source_gates=["delta_2134"],
        target_gates=[qd.id for qd in machine.quantum_dots.values()],
        layer_id="quantum_dot_pair_detuning_matrix",
        matrix=inverse_matrix[3:4, :4],
    )

    return machine


def update_detuning_axis(
    machine: LossDiVincenzoQuam,
    full_matrix: List[List[float]],
):
    vgs = machine.virtual_gate_sets[next(iter(machine.virtual_gate_sets))]
    target_gates = [qd.id for qd in machine.quantum_dots.values()]
    for i, qdp in enumerate(machine.quantum_dot_pairs.values()):
        source_gates = [qdp.detuning_axis_name]
        matrix = full_matrix[i : i + 1, :4]
        vgs.add_to_layer(
            source_gates=source_gates,
            target_gates=target_gates,
            matrix=matrix,
            layer_id="quantum_dot_pair_detuning_matrix",
        )


# pylint: disable-next=too-many-statements
def test_machine(
    machine: LossDiVincenzoQuam,
) -> None:
    """Update representative parameters, save to disk, reload, and verify round-trip.

    Covers every major parameter category:
    - State macro timing (ramp_duration, buffer_duration, hold_duration)
    - XY drive calibration via the macro update() API
    - Direct pulse attribute modification
    - Qubit physical properties (T1, T2, larmor_frequency)
    - Machine-level field (b_field)
    - Sensor readout parameters (threshold, pulse amplitude/length)
    - Cross-compensation / virtualization matrix
    - Named voltage tuning points
    """
    q1 = machine.qubits["q1"]
    q2 = machine.qubits["q2"]

    # ── 1. State macro timing ─────────────────────────────────────────
    # update() persistently sets calibration fields on the underlying macro.
    q1.macros[VoltagePointName.INITIALIZE].update(ramp_duration=64, hold_duration=100)
    q1.macros[VoltagePointName.MEASURE].update(buffer_duration=240)
    q1.macros[VoltagePointName.EMPTY].update(hold_duration=80)

    # ── 2. XY drive calibration via macro update() API ────────────────
    # update() on the XY-drive macro is the single entry-point for persistent
    # calibration: pi_amplitude sets the x180 pulse amplitude (x90 gets half),
    # duration rescales the pulse length/sigma, and frequency sets
    # qubit.larmor_frequency (the IF is derived as larmor - LO).
    xy_macro = q1.macros[SingleQubitMacroName.XY_DRIVE]
    xy_macro.update(pi_amplitude=0.5, duration=400, frequency=4.5e9)
    # Capture the transformed pulse length for later verification (the macro
    # quantises nanoseconds to clock-cycle units internally).
    expected_pulse_length = q1.xy.operations[f"{DrivePulseName.GAUSSIAN}_x90"].length

    # frequency_offset adds a delta to the current larmor_frequency instead
    # of replacing it -- handy for fine-tuning after an initial calibration.
    q2_xy = q2.macros[SingleQubitMacroName.XY_DRIVE]
    q2_xy.update(frequency=4.5e9)
    q2_xy.update(frequency_offset=1.5e6)

    # ── 3. Direct pulse attribute modification on q2 ──────────────────
    # Pulse objects on qubit.xy.operations can also be edited in place.
    q2.xy.operations[f"{DrivePulseName.GAUSSIAN}_x90"].amplitude = 0.17

    # ── 4. Qubit physical properties ──────────────────────────────────
    q1.T1 = 1e-6
    q1.T2ramsey = 0.5e-6
    q1.T2echo = 2e-6

    # ── 5. Machine-level property ─────────────────────────────────────
    machine.b_field = 0.15

    # ── 6. Sensor readout parameters ──────────────────────────────────
    sensor_name = next(iter(machine.sensor_dots))
    sensor = machine.sensor_dots[sensor_name]
    sensor.readout_resonator.operations["readout"].amplitude = 0.35
    sensor.readout_resonator.operations["readout"].length = 3000
    # Readout thresholds are keyed by quantum-dot-pair ID.
    pair_id = next(iter(machine.quantum_dot_pairs))
    sensor.readout_thresholds[pair_id] = 0.42

    # ── 7. Virtualization matrix (cross-compensation) ─────────────────
    # Replace the first-layer matrix with identity + 2 % cross-talk.
    gate_set_name = next(iter(machine.virtual_gate_sets))
    layer = machine.virtual_gate_sets[gate_set_name].layers[0]
    n_src, n_tgt = len(layer.source_gates), len(layer.target_gates)
    cross_talk_matrix = [[1.0 if i == j else 0.02 for j in range(n_tgt)] for i in range(n_src)]
    machine.update_full_cross_compensation(cross_talk_matrix, gate_set_name, target="opx")

    # ── 8. Named voltage tuning points ────────────────────────────────
    # add_point registers a VoltageTuningPoint in the VirtualGateSet,
    # stored under the key "{dot_id}_{point_name}".
    dot_id = q1.quantum_dot.id
    q1.add_point(VoltagePointName.INITIALIZE, {dot_id: 0.10}, duration=200)
    q1.add_point(VoltagePointName.MEASURE, {dot_id: 0.15}, duration=200)
    q1.add_point(VoltagePointName.EMPTY, {dot_id: 0.00}, duration=200)

    # ═══════════════════════════════════════════════════════════════════
    #  Save, reload, and verify every parameter round-trips cleanly.
    # ═══════════════════════════════════════════════════════════════════
    with tempfile.TemporaryDirectory() as save_dir:
        machine.save(save_dir)
        loaded = LossDiVincenzoQuam.load(save_dir)

    lq1 = loaded.qubits["q1"]
    lq2 = loaded.qubits["q2"]

    # -- State macros --
    assert lq1.macros[VoltagePointName.INITIALIZE].ramp_duration == 64
    assert lq1.macros[VoltagePointName.INITIALIZE].hold_duration == 100
    assert lq1.macros[VoltagePointName.MEASURE].buffer_duration == 240
    assert lq1.macros[VoltagePointName.EMPTY].hold_duration == 80

    # -- XY drive calibration (amplitude, duration, frequency) --
    assert lq1.xy.operations[f"{DrivePulseName.GAUSSIAN}_x90"].amplitude == 0.25
    assert lq1.xy.operations[f"{DrivePulseName.GAUSSIAN}_x90"].length == expected_pulse_length
    assert lq1.larmor_frequency == 4.5e9
    assert lq2.larmor_frequency == 4.5e9 + 1.5e6  # base + offset

    # -- Direct pulse --
    assert lq2.xy.operations[f"{DrivePulseName.GAUSSIAN}_x90"].amplitude == 0.17

    # -- Qubit properties --
    assert lq1.T1 == 1e-6
    assert lq1.T2ramsey == 0.5e-6
    assert lq1.T2echo == 2e-6

    # -- Machine property --
    assert loaded.b_field == 0.15

    # -- Sensor readout --
    l_sensor = loaded.sensor_dots[sensor_name]
    assert l_sensor.readout_resonator.operations["readout"].amplitude == 0.35
    assert l_sensor.readout_resonator.operations["readout"].length == 3000
    assert l_sensor.readout_thresholds[pair_id] == 0.42

    # -- Virtualization matrix --
    l_layer = loaded.virtual_gate_sets[gate_set_name].layers[0]
    for i, row in enumerate(l_layer.matrix):
        for j, val in enumerate(row):
            expected = 1.0 if i == j else 0.02
            assert abs(val - expected) < 1e-9, f"matrix[{i}][{j}]: {val} != {expected}"

    # -- Voltage points --
    init_name = f"{dot_id}_{VoltagePointName.INITIALIZE}"
    l_vgs = loaded.virtual_gate_sets[gate_set_name]
    assert init_name in l_vgs.macros, f"point '{init_name}' missing after reload"
    assert l_vgs.macros[init_name].voltages[dot_id] == 0.10
    assert l_vgs.macros[init_name].duration == 200

    print("All round-trip assertions passed.")
    return loaded


if __name__ == "__main__":
    path = Path(__file__).resolve().parent / "quam_state"

    machine = build_machine(path)
    machine = populate_machine(machine)
    machine.save(path)
    config = machine.generate_config()
    machine.save("/Users/kalidu_laptop/Tutorial_Quam_State")
