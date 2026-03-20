"""Full workflow example: wiring, macros, pulses, and overrides.

This script demonstrates the complete end-to-end workflow for building
a Loss-DiVincenzo qubit machine with default macros and pulses, and
shows how to:

1. Wire a Loss-DiVincenzo qubit machine (combined single-stage workflow).
2. Wire default macros via ``wire_machine_macros()``.
3. Update an operation parameter (e.g. ramp_duration, default_amplitude_scale).
4. Update the drive pulse type (e.g. swap Gaussian for DRAG).
5. Replace a particular macro (instance-level and type-level overrides).
"""

# pylint: disable=no-member
# pylint: disable=too-many-ancestors

from __future__ import annotations

from typing import Dict

import numpy as np
from qm import qua
from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam.components import pulses
from quam.components.macro import QubitPairMacro

from quam_builder.architecture.quantum_dots.components import QPU
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    SingleQubitMacroName,
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    X180Macro,
)
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, LossDiVincenzoQuam
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots import build_quam


########################################################################################################################
# %%                                           Static parameters
########################################################################################################################

host_ip = "172.16.33.115"
cluster_name = "CS_3"

global_gates = [1, 2]
sensor_dots = [1, 2]
quantum_dots = [1, 2, 3]
quantum_dot_pairs = [(1, 2), (2, 3)]

qubit_pair_sensor_map = {
    "q1_q2": ["sensor_1"],
    "q2_q3": ["sensor_2"],
}


########################################################################################################################
# %%                          STEP 1: Wire a Loss-DiVincenzo qubit machine
########################################################################################################################


def build_wired_machine() -> LossDiVincenzoQuam:
    """Build a machine using the combined single-stage workflow.

    This creates connectivity with all components (dots, sensors, drive lines)
    in one go, allocates wiring, and builds the full Loss-DiVincenzo QUAM.
    """
    print("=" * 80)
    print("STEP 1: Build wired Loss-DiVincenzo machine")
    print("=" * 80)

    instruments = Instruments()
    instruments.add_mw_fem(controller=1, slots=[1])
    instruments.add_lf_fem(controller=1, slots=[2, 3])

    connectivity = Connectivity()
    connectivity.add_voltage_gate_lines(voltage_gates=global_gates, name="rb")
    connectivity.add_sensor_dots(
        sensor_dots=sensor_dots, shared_resonator_line=False, use_mw_fem=False
    )
    connectivity.add_quantum_dots(
        quantum_dots=quantum_dots,
        add_drive_lines=True,
        use_mw_fem=True,
        shared_drive_line=True,
    )
    connectivity.add_quantum_dot_pairs(quantum_dot_pairs=quantum_dot_pairs)

    allocate_wiring(connectivity, instruments)

    machine = BaseQuamQD()
    machine = build_quam_wiring(connectivity, host_ip, cluster_name, machine)
    machine = build_quam(
        machine,
        qubit_pair_sensor_map=qubit_pair_sensor_map,
        connect_qdac=False,
        save=False,
    )

    print(f"  Qubits: {list(machine.qubits.keys())}")
    print(f"  Qubit pairs: {list(machine.qubit_pairs.keys())}")
    print(f"  Sensor dots: {list(machine.sensor_dots.keys())}")
    return machine


########################################################################################################################
# %%                          STEP 2: Wire default macros
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
    print("\n" + "=" * 80)
    print("STEP 2: Wire default macros and pulses")
    print("=" * 80)

    wire_machine_macros(machine)

    q1 = machine.qubits["q1"]
    print(f"  q1 macros: {sorted(q1.macros.keys())}")
    print(f"  q1 xy_drive pulse: {type(q1.xy.operations.get(DrivePulseName.GAUSSIAN)).__name__}")
    print(
        f"  q1 reference_pulse_name: {q1.macros[SingleQubitMacroName.XY_DRIVE].reference_pulse_name}"
    )


########################################################################################################################
# %%                          STEP 3: Update operation parameters
########################################################################################################################


def update_operation_parameters(machine: LossDiVincenzoQuam) -> None:
    """Update parameters on already-wired default macro instances.

    After wiring, macro objects are accessible via ``qubit.macros[name]``.
    Their parameters can be tuned directly without re-wiring.
    """
    print("\n" + "=" * 80)
    print("STEP 3: Update operation parameters")
    print("=" * 80)

    for qubit in machine.qubits.values():
        # Tune initialize ramp duration
        qubit.macros[VoltagePointName.INITIALIZE].ramp_duration = 64

        # Tune measure hold duration
        qubit.macros[VoltagePointName.MEASURE].hold_duration = 240

        # Apply a calibrated multiplicative scale on top of the reference pulse.
        qubit.macros[SingleQubitMacroName.XY_DRIVE].default_amplitude_scale = 0.85

        # Set identity wait duration
        qubit.macros[SingleQubitMacroName.IDENTITY].duration = 24

    q1 = machine.qubits["q1"]
    print(f"  q1.initialize.ramp_duration = {q1.macros[VoltagePointName.INITIALIZE].ramp_duration}")
    print(f"  q1.measure.hold_duration = {q1.macros[VoltagePointName.MEASURE].hold_duration}")
    print(
        "  q1.xy_drive.default_amplitude_scale = "
        f"{q1.macros[SingleQubitMacroName.XY_DRIVE].default_amplitude_scale}"
    )
    print(f"  q1.I.duration = {q1.macros[SingleQubitMacroName.IDENTITY].duration}")


########################################################################################################################
# %%                     STEP 4: Update the drive pulse type (Gaussian -> DRAG)
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
    print("STEP 4: Update drive pulse type (Gaussian -> DRAG)")
    print("=" * 80)

    for qubit in machine.qubits.values():
        if qubit.xy is None:
            continue

        # 1. Register a DRAG pulse alongside the existing Gaussian
        qubit.xy.operations[DrivePulseName.DRAG] = pulses.DragPulse(
            length=500,
            amplitude=0.25,
            sigma=83,
            alpha=0.5,
            anharmonicity=-200e6,
            detuning=0,
        )

        # 2. Point the macro at the new pulse
        qubit.macros[SingleQubitMacroName.XY_DRIVE].reference_pulse_name = DrivePulseName.DRAG

    q1 = machine.qubits["q1"]
    print(f"  q1.xy.operations keys: {sorted(q1.xy.operations.keys())}")
    print(
        f"  q1.xy_drive.reference_pulse_name = {q1.macros[SingleQubitMacroName.XY_DRIVE].reference_pulse_name}"
    )
    print(f"  Both gaussian and drag are registered; macro now uses drag.")
    print(f"  All gates (x90, y180, etc.) derive from the drag pulse automatically.")


########################################################################################################################
# %%                     STEP 5: Replace a particular macro
########################################################################################################################


class TunedX180Macro(X180Macro):
    """Custom X180 macro with extra multiplicative amplitude scaling."""

    default_amplitude_scale: float = 0.78


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
    print("STEP 5: Replace macros (instance + type overrides)")
    print("=" * 80)

    wire_machine_macros(
        machine,
        macro_overrides={
            # Type-level: replace CZ on ALL qubit pairs
            "component_types": {
                "LDQubitPair": {
                    "macros": {
                        TwoQubitMacroName.CZ: {"factory": DemoCZMacro},
                    }
                },
            },
            # Instance-level: replace X180 on q1 only
            "instances": {
                "qubits.q1": {
                    "macros": {
                        SingleQubitMacroName.X_180: {"factory": TunedX180Macro},
                    }
                },
            },
        },
        strict=True,
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
    machine = build_wired_machine()
    wire_defaults(machine)
    update_operation_parameters(machine)
    update_drive_pulse_type(machine)
    replace_macros(machine)

    print("\n" + "=" * 80)
    print("All steps completed successfully.")
    print("=" * 80)


if __name__ == "__main__":
    main()
