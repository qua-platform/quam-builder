"""Example: wire, parameterize, and use built-in default macros (no overrides).

This script demonstrates:
1. Building a machine via the combined wiring workflow.
2. Wiring architecture defaults with ``wire_machine_macros(machine)`` only.
3. Parameterizing instantiated default macro objects and reference pulses directly on components.
4. Building a QUA program that calls those default macros.
5. Printing that program with ``generate_qua_script`` so the ``play``, ``ramp``, and ``wait`` calls from each ``apply`` method are visible.
"""

from __future__ import annotations

from qm import generate_qua_script, qua

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    SingleQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam


def parameterize_default_macros(machine: LossDiVincenzoQuam) -> None:
    """Tune parameters on already-wired default macro instances and pulses."""
    for qubit in machine.qubits.values():
        qubit.macros[VoltagePointName.INITIALIZE].ramp_duration = 64
        qubit.macros[VoltagePointName.MEASURE].buffer_duration = 240
        qubit.xy.operations[f"{DrivePulseName.GAUSSIAN}_x90"].amplitude = 0.0085
        qubit.macros[SingleQubitMacroName.IDENTITY].duration = 24


def print_macro_parameters(machine: LossDiVincenzoQuam) -> None:
    """Print key default-macro class bindings and tuned parameters."""
    q1 = machine.qubits["q1"]
    print("\n=== Default Macro Parameterization ===")
    print("q1.initialize class:", type(q1.macros[VoltagePointName.INITIALIZE]).__name__)
    print("q1.xy_drive class:", type(q1.macros[SingleQubitMacroName.XY_DRIVE]).__name__)
    print("q1.I class:", type(q1.macros[SingleQubitMacroName.IDENTITY]).__name__)
    print(
        "q1.initialize.ramp_duration:",
        q1.macros[VoltagePointName.INITIALIZE].ramp_duration,
    )
    print(
        "q1.measure.buffer_duration:",
        q1.macros[VoltagePointName.MEASURE].buffer_duration,
    )
    print(
        "q1.gaussian_x90.amplitude:",
        q1.xy.operations[f"{DrivePulseName.GAUSSIAN}_x90"].amplitude,
    )
    print("q1.I.duration:", q1.macros[SingleQubitMacroName.IDENTITY].duration)


def build_program(machine: LossDiVincenzoQuam):
    """Build a QUA program that uses default macros only."""
    q1 = machine.qubits["q1"]

    with qua.program() as prog:
        q1.initialize()
        qua.align()
        q1.x90()
        q1.I()
        q1.y90()
        qua.align()
        q1.measure()

    return prog


def main() -> None:
    machine = build_tutorial_machine()

    # Re-wire to demonstrate explicit default wiring (idempotent).
    wire_machine_macros(machine)

    parameterize_default_macros(machine)
    print_macro_parameters(machine)

    program = build_program(machine)
    print(
        "\n=== QUA program from parameterized default macros ===\n"
        + generate_qua_script(program)
    )


if __name__ == "__main__":
    main()
