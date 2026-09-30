"""Example: virtual gates on the tutorial machine.

``build_tutorial_machine()`` creates ``machine.virtual_gate_sets["main_qpu"]``
with two layers:

* ``compensation_layer`` starts as an identity. Each virtual name drives one
  physical gate. Cross-talk is written into this layer with
  ``update_cross_compensation_submatrix``.
* ``quantum_dot_pair_detuning_matrix`` is the detuning axis the builder
  registers for the dot pair (``epsilon = virtual_dot_1 - virtual_dot_2``).

The script resolves a virtual plunger before and after cross-talk, resolves
the detuning axis, then steps to that detuning in a QUA program.
"""

from __future__ import annotations

import matplotlib
from qm import qua

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)
from quam_builder.builder.quantum_dots.build_utils import DEFAULT_GATE_SET_ID

_DOT_PREFIX = "virtual_dot_"


def _print_voltages(title: str, voltages: dict) -> None:
    print(title)
    shown = False
    for name in sorted(voltages):
        value = float(voltages[name])
        if abs(value) < 1e-9:
            continue
        print(f"  {name}: {value:.4f} V")
        shown = True
    if not shown:
        print("  (all physical gates at 0 V)")


def _dot_pairs(gate_set):
    """Return ``(virtual_name, physical_channel)`` for the dot plungers."""
    layer = gate_set.layers[0]
    pairs = []
    for virtual_name, physical_name in zip(layer.source_gates, layer.target_gates):
        if str(virtual_name).startswith(_DOT_PREFIX):
            pairs.append((virtual_name, gate_set.channels[physical_name]))
    return pairs


def _show_matrix(layer) -> None:
    """Draw the compensation matrix when the backend can display it."""
    _fig, _ax = layer.plot_matrix(title=f"Layer {layer.id}")
    if matplotlib.get_backend().lower() == "agg":
        matplotlib.pyplot.close(_fig)
        print(f"Matrix plot for layer {layer.id!r} skipped (non-interactive backend).")
        return
    matplotlib.pyplot.show()


def main() -> None:
    machine = build_tutorial_machine()
    gate_set = machine.virtual_gate_sets[DEFAULT_GATE_SET_ID]
    layer = gate_set.layers[0]
    dot_names = [name for name, _channel in _dot_pairs(gate_set)]
    dot_channels = [channel for _name, channel in _dot_pairs(gate_set)]

    print("=== 1. Gate set from the builder ===")
    print(f"id: {gate_set.id}")
    print(f"physical gates: {list(gate_set.channels)}")
    for existing in gate_set.layers:
        print(f"layer {existing.id!r}")
        print(f"  virtual sources: {list(existing.source_gates)}")
        print(f"  targets: {list(existing.target_gates)}")
        print(f"  matrix: {existing.matrix}")

    print("\n=== 2. Identity: one virtual plunger, one physical plunger ===")
    identity = gate_set.resolve_voltages({dot_names[0]: 0.10})
    _print_voltages(f"resolve {dot_names[0]} = 0.10 V", identity)

    print("\n=== 3. Cross-talk on the two dot plungers ===")
    # Rows follow the physical channels, columns follow the virtual names.
    # Off-diagonal entries mean one virtual plunger moves the other dot too.
    cross_talk = [
        [1.0, 0.25],
        [0.10, 1.0],
    ]
    machine.update_cross_compensation_submatrix(
        virtual_names=dot_names,
        channels=dot_channels,
        matrix=cross_talk,
        target="opx",
    )
    coupled = gate_set.resolve_voltages({dot_names[0]: 0.10})
    _print_voltages(f"resolve {dot_names[0]} = 0.10 V with cross-talk", coupled)
    _show_matrix(layer)

    print("\n=== 4. Detuning axis the builder already registered ===")
    # Compensation is put back to identity so the plungers show only detuning.
    machine.update_cross_compensation_submatrix(
        virtual_names=dot_names,
        channels=dot_channels,
        matrix=[[1.0, 0.0], [0.0, 1.0]],
        target="opx",
    )
    detuning = gate_set.layers[1]
    detuning_name = detuning.source_gates[0]
    print(
        f"{detuning_name} maps onto {list(detuning.target_gates)} "
        f"with matrix {detuning.matrix}."
    )
    print("The builder calls QuantumDotPair.define_detuning_axis([[1, -1]]).")
    print("One knob, two dots: the moves are equal and opposite.")
    detuned = gate_set.resolve_voltages({detuning_name: 0.04})
    _print_voltages(f"resolve {detuning_name} = 0.04 V", detuned)

    print("\n=== 5. Step to that detuning inside a QUA program ===")
    gate_set.add_point("detuned", {detuning_name: 0.04}, duration=200)
    sequence = machine.voltage_sequences[DEFAULT_GATE_SET_ID]
    with qua.program() as _program:
        sequence.step_to_point("detuned")
    print("Built a QUA program that steps the gate set to point 'detuned'.")


if __name__ == "__main__":
    main()
