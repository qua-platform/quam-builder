"""Example: wire, parameterize, and use built-in default macros (no overrides).

This script demonstrates:
1. Building a small two-qubit quantum-dots machine.
2. Wiring architecture defaults with ``wire_machine_macros(machine)`` only.
3. Parameterizing instantiated default macro objects directly on components.
4. Building a QUA program that calls those default macros.
"""

# pylint: disable=no-member  # WiringLineType enum members are runtime-only

from __future__ import annotations

from typing import Dict

import numpy as np
from qm import qua
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam.components import pulses

from quam_builder.architecture.quantum_dots.components import QPU
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    SingleQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, LossDiVincenzoQuam
from quam_builder.builder.quantum_dots.build_qpu_stage1 import _BaseQpuBuilder
from quam_builder.builder.quantum_dots.build_qpu_stage2 import _LDQubitBuilder


def _plunger_ports(qubit_id: str) -> Dict[str, str]:
    return {"opx_output": f"#/wiring/qubits/{qubit_id}/p/opx_output"}


def _mw_drive_ports(qubit_id: str) -> Dict[str, str]:
    return {"opx_output": f"#/wiring/qubits/{qubit_id}/xy/opx_output"}


def _barrier_ports(pair_id: str) -> Dict[str, str]:
    return {"opx_output": f"#/wiring/qubit_pairs/{pair_id}/b/opx_output"}


def build_demo_machine() -> LossDiVincenzoQuam:
    """Build a small machine with 2 qubits and 1 qubit pair."""
    machine = BaseQuamQD()
    machine.wiring = {
        "qubits": {
            "q1": {
                WiringLineType.PLUNGER_GATE.value: _plunger_ports("q1"),
                WiringLineType.DRIVE.value: _mw_drive_ports("q1"),
            },
            "q2": {
                WiringLineType.PLUNGER_GATE.value: _plunger_ports("q2"),
                WiringLineType.DRIVE.value: _mw_drive_ports("q2"),
            },
        },
        "qubit_pairs": {
            "q1_q2": {
                WiringLineType.BARRIER_GATE.value: _barrier_ports("q1_q2")
            },  # pylint: disable=no-member
        },
    }
    machine = _BaseQpuBuilder(machine).build()
    machine = _LDQubitBuilder(machine).build()

    if getattr(machine, "qpu", None) is None:
        machine.qpu = QPU()

    # Seed minimal reference pulse used by default XY macros.
    # Only one pulse is needed — XYDriveMacro scales amplitude for angle
    # and applies virtual-Z for rotation axis.
    for qubit in machine.qubits.values():
        if qubit.xy is None:
            continue
        qubit.xy.operations.setdefault(
            DrivePulseName.GAUSSIAN,
            pulses.GaussianPulse(length=64, amplitude=0.01, sigma=16),
        )

    # Defaults only: no profile and no runtime overrides.
    wire_machine_macros(machine)
    return machine


def add_default_state_points(machine: LossDiVincenzoQuam) -> None:
    """Define canonical voltage points consumed by state macros."""
    for qubit in machine.qubits.values():
        dot_id = qubit.quantum_dot.id
        qubit.with_step_point(VoltagePointName.INITIALIZE, {dot_id: 0.10}, duration=200)
        qubit.with_step_point(VoltagePointName.MEASURE, {dot_id: 0.15}, duration=220)
        qubit.with_step_point(VoltagePointName.EMPTY, {dot_id: 0.00}, duration=180)


def parameterize_default_macros(machine: LossDiVincenzoQuam) -> None:
    """Tune parameters on already-wired default macro instances."""
    for qubit in machine.qubits.values():
        qubit.macros[VoltagePointName.INITIALIZE].ramp_duration = 64
        qubit.macros[VoltagePointName.MEASURE].hold_duration = 240
        qubit.macros[SingleQubitMacroName.XY_DRIVE].default_amplitude_scale = 0.85
        # Identity duration may start as a reference; concretize before assigning numeric value.
        qubit.macros[SingleQubitMacroName.IDENTITY].duration = None
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
        "q1.measure.hold_duration:",
        q1.macros[VoltagePointName.MEASURE].hold_duration,
    )
    print(
        "q1.xy_drive.default_amplitude_scale:",
        q1.macros[SingleQubitMacroName.XY_DRIVE].default_amplitude_scale,
    )
    print("q1.I.duration:", q1.macros[SingleQubitMacroName.IDENTITY].duration)


def build_program(machine: LossDiVincenzoQuam):
    """Build a QUA program that uses default macros only."""
    q1 = machine.qubits["q1"]
    q2 = machine.qubits["q2"]

    with qua.program() as prog:
        q1.initialize()
        q2.initialize()
        q1.x90()
        q1.x(angle=-np.pi / 2)  # Negative-angle behavior comes from default XY logic.
        q2.y(angle=np.pi / 3)
        q1.z90()
        q2.I()
        q1.measure()
        q2.measure()

    return prog


def main() -> None:
    machine = build_demo_machine()
    add_default_state_points(machine)
    parameterize_default_macros(machine)
    print_macro_parameters(machine)

    _ = build_program(machine)
    print("\nBuilt QUA program successfully using parameterized default macros (no overrides).")


if __name__ == "__main__":
    main()
