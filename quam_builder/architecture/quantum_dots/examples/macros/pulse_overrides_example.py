"""Example: default XY pulses, editing anchors, and switching pulse family.

``wire_machine_macros(machine)`` registers, on each qubit XY drive, one
operation per gate for every pulse family (gaussian, square, kaiser,
hermite, drag), plus ``cz`` and ``crot``.

Within a family, ``{family}_x90`` and ``{family}_x180`` are the anchors.
The other gates (``x_neg90``, ``y90``, ``y180``, ``y_neg90``) reference
the anchor's length and amplitude, so editing the anchor updates them.

All families stay registered at once. ``machine.set_pulse_family(name)``
only changes which family the ``xy_drive`` macro resolves to; it does not
remove the others, so switching back and forth is instantaneous.
"""

from __future__ import annotations

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    SingleQubitMacroName,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam

_ANCHOR = "gaussian_x90"
_DERIVED = "gaussian_y90"


def print_gaussian_anchors(machine: LossDiVincenzoQuam, title: str) -> None:
    """Print the gaussian x90 anchor and the y90 gate that references it."""
    print(f"\n=== {title} ===")
    for qubit_id, qubit in machine.qubits.items():
        xy = getattr(qubit, "xy", None)
        if xy is None:
            continue
        for pulse_name in (_ANCHOR, _DERIVED):
            pulse = xy.operations[pulse_name]
            print(
                f"  {qubit_id}.{pulse_name}: {type(pulse).__name__}"
                f"(length={pulse.length}, amplitude={pulse.amplitude})"
            )


def _set_gaussian_x90(qubit, length: int, amplitude: float) -> None:
    """Edit the gaussian x90 anchor in place."""
    pulse = qubit.xy.operations[_ANCHOR]
    pulse.length = length
    pulse.amplitude = amplitude


def update_all_qubit_pulses(machine: LossDiVincenzoQuam) -> None:
    """Set the same gaussian x90 anchor on every qubit."""
    for qubit in machine.qubits.values():
        if getattr(qubit, "xy", None) is None:
            continue
        _set_gaussian_x90(qubit, length=500, amplitude=0.3)


def update_single_qubit_pulse(machine: LossDiVincenzoQuam) -> None:
    """Set a different gaussian x90 anchor on q1 only."""
    _set_gaussian_x90(machine.qubits["q1"], length=800, amplitude=0.15)


def switch_pulse_family(machine: LossDiVincenzoQuam) -> None:
    """Point every qubit's xy_drive macro at the kaiser family instead of gaussian."""
    machine.set_pulse_family(DrivePulseName.KAISER.value)

    q1 = machine.qubits["q1"]
    xy_macro = q1.macros[SingleQubitMacroName.XY_DRIVE]
    print(f"\n=== After switching to {DrivePulseName.KAISER.value} ===")
    print(f"  q1.xy_drive.pulse_family: {xy_macro.pulse_family}")
    print(f"  q1.xy_drive.pulse_name: {xy_macro.pulse_name}")
    print(f"  q1.xy.operations still has gaussian_x90: {'gaussian_x90' in q1.xy.operations}")


def main() -> None:
    machine = build_tutorial_machine()

    # Re-wire to demonstrate explicit default wiring (idempotent).
    wire_machine_macros(machine)

    print_gaussian_anchors(machine, "Default gaussian anchor")

    update_all_qubit_pulses(machine)
    print_gaussian_anchors(machine, "After updating every gaussian_x90")

    update_single_qubit_pulse(machine)
    print_gaussian_anchors(machine, "After updating q1 gaussian_x90 only")

    switch_pulse_family(machine)


if __name__ == "__main__":
    main()
