"""Add qubits by hand to the dot machine ``manual_dots_example.py`` saved.

Same device as ``wiring_two_stage_example.py`` Stage 2 (same qubit ids, same
MW-FEM ports, same qubit pairs) but every ``XYDriveMW`` and ``register_qubit``
call is written out explicitly instead of coming from wiring + a builder.

Run ``manual_dots_example.py`` first -- this script loads the state it saves.
"""

from __future__ import annotations

from quam_builder.architecture.quantum_dots.components import ExchangeAxis
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.qpu import ExchangeOnlyQuam

from quam_builder.architecture.quantum_dots.examples.connectivity.manual_dots_example import (
    STATE_PATH,
)

CON = "con1"


def load_dot_machine() -> ExchangeOnlyQuam:
    """Step 1: load the BaseQuamQD manual_dots_example.py saved; promote to LossDiVincenzoQuam."""
    if not STATE_PATH.exists():
        raise SystemExit(f"No saved state at {STATE_PATH}. Run manual_dots_example.py first.")
    return ExchangeOnlyQuam.load(str(STATE_PATH))


def register_qubits(machine: ExchangeOnlyQuam) -> None:
    """Step 2: Register Qubits with 2 QuantumDotPairs"""
    machine.register_qubit(
        qubit_name = "q1",
        jn_pair = "virtual_dot_1_virtual_dot_2_pair", 
        jz_pair = "virtual_dot_2_virtual_dot_3_pair",
    )
    machine.register_qubit(
        qubit_name = "q2",
        jn_pair = "virtual_dot_4_virtual_dot_5_pair", 
        jz_pair = "virtual_dot_5_virtual_dot_6_pair",
    )


def register_qubit_pairs(machine: ExchangeOnlyQuam) -> None:
    """Step 3: q1_q2, with virtual_barrier_3 in the middle, symmetrically

    register_qubit_pair() finds the matching QuantumDotPair by dot ids -- it
    was already registered (with its barrier and detuning axis) in
    manual_dots_example.py.
    """
    machine.register_qubit_pair(id="q1_q2", qubit_control_name="q1", qubit_target_name="q2", barrier_gate_name = "virtual_barrier_3")

def create_exchange_axes(machine: ExchangeOnlyQuam): 
    for qdp in machine.quantum_dot_pairs.values(): 
        if isinstance(qdp, ExchangeAxis):
            continue
        qdp.__class__ = ExchangeAxis
        qdp.add_exchange_axis()

def main() -> ExchangeOnlyQuam:
    machine = load_dot_machine()
    register_qubits(machine)
    register_qubit_pairs(machine)
    create_exchange_axes(machine)

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
