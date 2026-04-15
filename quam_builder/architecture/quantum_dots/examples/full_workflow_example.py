"""Full workflow example: wiring, macros, pulses, and overrides.

This script demonstrates the complete end-to-end workflow for a
Loss-DiVincenzo qubit machine with default macros and pulses:

1. Build the machine via the combined wiring workflow.
2. Wire default macros via ``wire_machine_macros()``.
3. Update operation parameters and the reference pulse itself.
4. Update the drive pulse type (e.g. swap Gaussian for DRAG).
5. Replace a particular macro (instance-level and type-level overrides).
"""

# pylint: disable=too-many-ancestors

from __future__ import annotations

from qm import qua
from quam.components import pulses
from quam.components.macro import QubitPairMacro

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.macro_catalog import (
    TypeOverrideCatalog,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    SingleQubitMacroName,
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    X180Macro,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qubit_pair.ld_qubit_pair import LDQubitPair
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam

########################################################################################################################
# %%                          STEP 1: Wire default macros
########################################################################################################################


def wire_defaults(machine: LossDiVincenzoQuam) -> None:
    """Wire all default macros and pulses onto the machine.

    ``wire_machine_macros()`` materializes defaults from the component catalog:
    - State macros (initialize, measure, empty) on qubits, pairs, dots
    - Single-qubit gate macros (xy_drive, x, y, z, x180, x90, ...) on qubits
    - Two-qubit gate placeholders (cnot, cz, swap, iswap) on qubit pairs
    - Default ``gaussian`` reference pulse on each qubit's XY drive
    - Default ``readout`` pulse on sensor dot resonators
    """
    print("=" * 80)
    print("STEP 1: Wire default macros and pulses")
    print("=" * 80)

    wire_machine_macros(machine)

    q1 = machine.qubits["q1"]
    print(f"  q1 macros: {sorted(q1.macros.keys())}")
    print(f"  q1 xy_drive pulse: {type(q1.xy.operations.get(DrivePulseName.GAUSSIAN)).__name__}")
    print(
        f"  q1 reference_pulse_name: {q1.macros[SingleQubitMacroName.XY_DRIVE].reference_pulse_name}"
    )


########################################################################################################################
# %%                          STEP 2: Update operation parameters
########################################################################################################################


def update_operation_parameters(machine: LossDiVincenzoQuam) -> None:
    """Update parameters on already-wired default macro instances.

    After wiring, macro objects are accessible via ``qubit.macros[name]``.
    Their parameters can be tuned directly without re-wiring.
    """
    print("\n" + "=" * 80)
    print("STEP 2: Update operation parameters")
    print("=" * 80)

    for qubit in machine.qubits.values():
        qubit.macros[VoltagePointName.INITIALIZE].ramp_duration = 64
        qubit.macros[VoltagePointName.MEASURE].buffer_duration = 240
        qubit.xy.operations[DrivePulseName.GAUSSIAN].amplitude = 0.17
        qubit.macros[SingleQubitMacroName.IDENTITY].duration = 24

    q1 = machine.qubits["q1"]
    print(f"  q1.initialize.ramp_duration = {q1.macros[VoltagePointName.INITIALIZE].ramp_duration}")
    print(f"  q1.measure.buffer_duration = {q1.macros[VoltagePointName.MEASURE].buffer_duration}")
    print("  q1.gaussian.amplitude = " f"{q1.xy.operations[DrivePulseName.GAUSSIAN].amplitude}")
    print(f"  q1.I.duration = {q1.macros[SingleQubitMacroName.IDENTITY].duration}")


########################################################################################################################
# %%                     STEP 3: Update the drive pulse type (Gaussian -> DRAG)
########################################################################################################################


def update_drive_pulse_type(machine: LossDiVincenzoQuam) -> None:
    """Replace the default Gaussian drive with a DRAG pulse.

    The ``XYDriveMacro`` uses ``reference_pulse_name`` to select which pulse
    from ``qubit.xy.operations`` is the single source of truth for all gates.

    To switch from Gaussian to DRAG:
    1. Register a DRAG pulse under ``DrivePulseName.DRAG``
    2. Update ``reference_pulse_name`` on the xy_drive macro

    All gate macros (x90, x180, y90, etc.) automatically pick up the change.
    """
    print("\n" + "=" * 80)
    print("STEP 3: Update drive pulse type (Gaussian -> DRAG)")
    print("=" * 80)

    for qubit in machine.qubits.values():
        if qubit.xy is None:
            continue

        qubit.xy.operations[DrivePulseName.DRAG] = pulses.DragPulse(
            length=500,
            amplitude=0.25,
            axis_angle=0.0,
            sigma=83,
            alpha=0.5,
            anharmonicity=-200e6,
            detuning=0,
        )

        qubit.macros[SingleQubitMacroName.XY_DRIVE].reference_pulse_name = DrivePulseName.DRAG

    q1 = machine.qubits["q1"]
    print(f"  q1.xy.operations keys: {sorted(q1.xy.operations.keys())}")
    print(
        f"  q1.xy_drive.reference_pulse_name = {q1.macros[SingleQubitMacroName.XY_DRIVE].reference_pulse_name}"
    )
    print("  Both gaussian and drag are registered; macro now uses drag.")
    print("  All gates (x90, y180, etc.) derive from the drag pulse automatically.")


########################################################################################################################
# %%                     STEP 4: Replace a particular macro
########################################################################################################################


class TunedX180Macro(X180Macro):
    """Custom X180 macro placeholder used for macro replacement examples."""

    pass


class DemoCZMacro(QubitPairMacro):
    """Demo CZ macro replacing the default placeholder."""

    duration_ns: int = 64

    @property
    def inferred_duration(self) -> float:
        return self.duration_ns * 1e-9

    def apply(self, duration_ns: int | None = None, **kwargs):
        duration = self.duration_ns if duration_ns is None else duration_ns
        duration_cycles = max(0, int(round(duration / 4.0)))
        control_xy = self.qubit_pair.qubit_control.xy.name
        target_xy = self.qubit_pair.qubit_target.xy.name
        qua.align(control_xy, target_xy)
        if duration_cycles > 0:
            qua.wait(duration_cycles, control_xy, target_xy)


def replace_macros(machine: LossDiVincenzoQuam) -> None:
    """Replace macros using instance-level and type-level overrides.

    Override precedence: instance > type > default
    """
    print("\n" + "=" * 80)
    print("STEP 4: Replace macros (instance + type overrides)")
    print("=" * 80)

    wire_machine_macros(
        machine,
        catalogs=[
            TypeOverrideCatalog(
                {
                    LDQubitPair: {
                        TwoQubitMacroName.CZ: DemoCZMacro,
                    },
                }
            ),
        ],
        instance_overrides={
            "qubits.q1": {
                SingleQubitMacroName.X_180: TunedX180Macro,
            },
        },
    )

    q1 = machine.qubits["q1"]
    q2 = machine.qubits["q2"]
    pair = machine.qubit_pairs["q1_q2"]

    print(
        "  q1.x180 class: " f"{type(q1.macros[SingleQubitMacroName.X_180]).__name__} (overridden)"
    )
    print("  q2.x180 class: " f"{type(q2.macros[SingleQubitMacroName.X_180]).__name__} (default)")
    print("  q1_q2.cz class: " f"{type(pair.macros[TwoQubitMacroName.CZ]).__name__} (overridden)")


########################################################################################################################
# %%                                           Main
########################################################################################################################


def main() -> None:
    machine = build_tutorial_machine()
    wire_defaults(machine)
    update_operation_parameters(machine)
    update_drive_pulse_type(machine)
    replace_macros(machine)

    print("\n" + "=" * 80)
    print("All steps completed successfully.")
    print("=" * 80)


if __name__ == "__main__":
    main()
