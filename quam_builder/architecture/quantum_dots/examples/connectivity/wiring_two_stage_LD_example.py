"""Build the same machine as ``wiring_combined_example.py``, in two stages.

Use this workflow when you want to tune quantum dots (plungers, barriers,
sensors, QDAC) **before** committing to qubit drive lines:

- Stage 1 (``build_base_quam``): dot-layer connectivity only, no drive
  lines. Saves a ``BaseQuamQD``.
- Stage 2 loads that saved state, allocates only the MW drive lines, and
  promotes it with ``build_loss_divincenzo_quam``. The dot layer is not
  allocated again.

The dot-layer connectivity matches ``wiring_combined_example.py`` (same
elements, same order, same QDAC constraints), so the saved machine and the
combined build land on the same ports.
"""

from __future__ import annotations

import os
from pathlib import Path

from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring
from qualang_tools.wirer.wirer.channel_specs import lf_fem_spec, qdac2_spec

from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, LossDiVincenzoQuam
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.qop_connectivity.create_wiring import create_wiring
from quam_builder.builder.quantum_dots import build_base_quam, build_loss_divincenzo_quam

from quam_builder.architecture.quantum_dots.examples.connectivity.wiring_combined_LD_example import (
    QUANTUM_DOTS,
    QUANTUM_DOT_PAIRS,
    SENSOR_DOTS,
    TRIGGERED_DOTS,
    QUBIT_PAIR_SENSOR_MAP,
    configure_sensor_readout,
    qdac_config,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[1]
STATE_PATH = EXAMPLES_DIR / "quam_state" / "wiring_two_stage"


def declare_dot_layer_connectivity() -> Connectivity:
    """Stage 1 connectivity: dots, barriers, sensors, QDAC. No drive lines."""
    connectivity = Connectivity()
    connectivity.add_sensor_dot_voltage_gate_lines(
        SENSOR_DOTS, constraints=lf_fem_spec() & qdac2_spec()
    )
    connectivity.add_sensor_dot_resonator_line(SENSOR_DOTS, shared_line=False)
    connectivity.add_quantum_dot_voltage_gate_lines(
        TRIGGERED_DOTS, triggered=True, constraints=lf_fem_spec() & qdac2_spec()
    )
    remaining_dots = [d for d in QUANTUM_DOTS if d not in TRIGGERED_DOTS]
    connectivity.add_quantum_dot_voltage_gate_lines(
        remaining_dots, constraints=lf_fem_spec() & qdac2_spec()
    )
    connectivity.add_barrier_voltage_gate_lines(
        QUANTUM_DOT_PAIRS, constraints=lf_fem_spec() & qdac2_spec()
    )
    return connectivity


def build_stage1() -> Path:
    """Stage 1: dots, barriers, sensors, and the QDAC. No qubits yet.

    The machine is saved so stage 2 can run later, in another process.
    """
    connectivity = declare_dot_layer_connectivity()

    instruments = Instruments()
    instruments.add_lf_fem(controller=1, slots=[2, 3])
    instruments.add_qdac2(indices=[1])
    allocate_wiring(connectivity, instruments)

    os.makedirs(STATE_PATH, exist_ok=True)
    machine = build_quam_wiring(
        connectivity,
        host_ip="127.0.0.1",
        cluster_name="tutorial",
        quam_instance=BaseQuamQD(),
        dac_config={"qdac1": qdac_config("127.0.0.2")},
        path=str(STATE_PATH),
    )
    machine = build_base_quam(machine, save=False)
    configure_sensor_readout(machine)
    machine.save(str(STATE_PATH))
    print(f"Stage 1 saved to {STATE_PATH}")
    print(f"  {list(machine.quantum_dots)}, {list(machine.sensor_dots)} (no qubits yet)")
    return STATE_PATH


def attach_drive_lines(machine: BaseQuamQD) -> None:
    """Allocate MW drive lines and add them to the loaded machine's wiring.

    The dot-layer wiring (plungers, barriers, sensors, QDAC) stays as it was
    saved. Only the new drive entries are written in.
    """
    connectivity = Connectivity()
    connectivity.add_quantum_dot_drive_lines(QUANTUM_DOTS, shared_line=False, use_mw_fem=True)

    instruments = Instruments()
    instruments.add_mw_fem(controller=1, slots=[1])
    allocate_wiring(connectivity, instruments)

    drive_wiring = create_wiring(connectivity)
    for qubit_id, lines in drive_wiring["qubits"].items():
        qubit_wiring = machine.wiring["qubits"][qubit_id]
        for line_type, ports in lines.items():
            qubit_wiring[line_type] = ports


def build_stage2(state_path: Path) -> LossDiVincenzoQuam:
    """Stage 2: load the saved dot machine, add drive lines, promote to qubits."""
    machine = BaseQuamQD.load(str(state_path))
    attach_drive_lines(machine)
    machine = build_loss_divincenzo_quam(
        machine,
        qubit_pair_sensor_map=QUBIT_PAIR_SENSOR_MAP,
        save=False,
    )
    # Stage 2 wires pair-specific readout pulses. Re-apply the tank settings
    # so those pulses match the 0.3 V / 2500 ns readout saved in stage 1.
    configure_sensor_readout(machine)
    print(f"Stage 2: {list(machine.qubits)}, {list(machine.qubit_pairs)}")
    return machine


def main() -> LossDiVincenzoQuam:
    state_path = build_stage1()
    machine_stage2 = build_stage2(state_path)

    # Real connection (needs a live QOP + QDAC-II on the network):
    # machine_stage2.connect()
    # machine_stage2.connect_to_external_source()
    # machine_stage2.save()
    return machine_stage2


if __name__ == "__main__":
    main()
