"""Add qubits by hand to the dot machine ``manual_dots_example.py`` saved.

Same device as ``wiring_two_stage_example.py`` Stage 2 (same qubit ids, same
MW-FEM ports, same qubit pairs) but every ``XYDriveMW`` and ``register_qubit``
call is written out explicitly instead of coming from wiring + a builder.

Run ``manual_dots_example.py`` first -- this script loads the state it saves.
"""

from __future__ import annotations

from quam.components.ports import MWFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import XYDriveMW
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam

from quam_builder.architecture.quantum_dots.examples.connectivity.manual_dots_example import (
    STATE_PATH,
)

CON = "con1"
MW_FEM = 1


def load_dot_machine() -> LossDiVincenzoQuam:
    """Step 1: load the BaseQuamQD manual_dots_example.py saved; promote to LossDiVincenzoQuam."""
    if not STATE_PATH.exists():
        raise SystemExit(f"No saved state at {STATE_PATH}. Run manual_dots_example.py first.")
    return LossDiVincenzoQuam.load(str(STATE_PATH))


def register_qubits(machine: LossDiVincenzoQuam) -> None:
    """Step 2: one XYDriveMW per dot, on MW-FEM ports 1-4 (matches the wirer path)."""
    for i in range(1, 5):
        xy = XYDriveMW(
            id=f"Q{i}_xy",
            opx_output=MWFEMAnalogOutputPort(
                CON, MW_FEM, port_id=i, band=1, upconverter_frequency=5e9
            ),
            intermediate_frequency=5e6 + i * 1e6,  # placeholder; calibrate per qubit
        )
        machine.register_qubit(
            quantum_dot_id=f"virtual_dot_{i}",
            qubit_name=f"q{i}",
            xy=xy,
        )

    # Readout goes through the partner dot in the same pair.
    machine.qubits["q1"].preferred_readout_quantum_dot = "virtual_dot_2"
    machine.qubits["q2"].preferred_readout_quantum_dot = "virtual_dot_1"
    machine.qubits["q3"].preferred_readout_quantum_dot = "virtual_dot_4"
    machine.qubits["q4"].preferred_readout_quantum_dot = "virtual_dot_3"


def register_qubit_pairs(machine: LossDiVincenzoQuam) -> None:
    """Step 3: q1_q2 on the (1,2) barrier, q3_q4 on the (3,4) barrier.

    register_qubit_pair() finds the matching QuantumDotPair by dot ids -- it
    was already registered (with its barrier and detuning axis) in
    manual_dots_example.py.
    """
    machine.register_qubit_pair(id="q1_q2", qubit_control_name="q1", qubit_target_name="q2")
    machine.register_qubit_pair(id="q3_q4", qubit_control_name="q3", qubit_target_name="q4")


def main() -> LossDiVincenzoQuam:
    machine = load_dot_machine()
    register_qubits(machine)
    register_qubit_pairs(machine)

    # Re-run so the new qubits/pairs get default macros and pulses too.
    wire_machine_macros(machine, fill_only=False)

    print(f"qubits: {list(machine.qubits)}")
    print(f"qubit_pairs: {list(machine.qubit_pairs)}")

    # Real connection (needs a live QOP + QDAC-II on the network):
    # machine.connect()
    # machine.connect_to_external_source()
    # machine.save()
    return machine


if __name__ == "__main__":
    main()
