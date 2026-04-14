"""Example: default pulse wiring and direct pulse configuration.

Demonstrates pulse management:

1. ``wire_machine_macros(machine)`` -- adds default ``gaussian`` pulse to XY drives.
2. Direct manipulation of pulse objects on channels.

Only one reference pulse (``gaussian``) is registered per qubit by default.
``XYDriveMacro`` scales amplitude for rotation angle and applies virtual-Z
for rotation axis, so all single-qubit gates derive from this single pulse.
"""

from __future__ import annotations

from quam.components.pulses import GaussianPulse

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam


def print_pulse_summary(machine: LossDiVincenzoQuam, title: str) -> None:
    """Print pulse operations for each qubit's XY drive."""
    print(f"\n=== {title} ===")
    for qubit_id, qubit in machine.qubits.items():
        xy = getattr(qubit, "xy", None)
        if xy is None:
            continue
        ops = getattr(xy, "operations", {})
        print(f"\n  {qubit_id}.xy.operations:")
        for pulse_name, p in sorted(ops.items()):
            cls_name = type(p).__name__
            length = getattr(p, "length", "?")
            amp = getattr(p, "amplitude", "?")
            axis = getattr(p, "axis_angle", "N/A")
            print(
                f"    {pulse_name:>10s}: {cls_name}(length={length}, amplitude={amp}, axis_angle={axis})"
            )


def update_all_qubit_pulses(machine: LossDiVincenzoQuam) -> None:
    """Update the gaussian pulse on all qubits directly.

    After wiring, pulse objects are accessible on the channel's operations dict.
    Modify them in place or replace with new instances.
    """
    for qubit in machine.qubits.values():
        xy = getattr(qubit, "xy", None)
        if xy is None:
            continue
        xy.operations["gaussian"] = GaussianPulse(
            length=500,
            amplitude=0.3,
            sigma=83,
        )


def update_single_qubit_pulse(machine: LossDiVincenzoQuam) -> None:
    """Override gaussian on q1 only."""
    q1 = machine.qubits["q1"]
    q1.xy.operations["gaussian"] = GaussianPulse(
        length=800,
        amplitude=0.15,
        sigma=133,
    )


def main() -> None:
    machine = build_tutorial_machine()

    # Re-wire to demonstrate explicit default wiring (idempotent).
    wire_machine_macros(machine)

    print_pulse_summary(machine, "Default Pulse")

    update_all_qubit_pulses(machine)
    print_pulse_summary(machine, "After Updating All Qubit Pulses")

    update_single_qubit_pulse(machine)
    print_pulse_summary(machine, "After Updating q1 Pulse Only")


if __name__ == "__main__":
    main()
