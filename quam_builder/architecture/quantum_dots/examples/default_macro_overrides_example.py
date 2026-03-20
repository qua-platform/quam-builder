"""Example: default macro wiring plus selective and type-level overrides.

This script demonstrates:
1. Building a small two-qubit quantum-dots machine.
2. Using default supported macros.
3. Overriding only one macro while keeping all other defaults.
4. Overriding a macro for all components of a given type.
5. Building a QUA program that uses the wired macros.
"""

# pylint: disable=no-member  # WiringLineType enum members are runtime-only

# Macro classes in this demo inherit from framework mixins with deep MRO.
# pylint: disable=too-many-ancestors

from __future__ import annotations

from typing import Dict

from qm import qua
from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType
from quam.components import pulses
from quam.components.macro import QubitPairMacro

from quam_builder.architecture.quantum_dots.components import QPU
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    X180Macro,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    InitializeStateMacro,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    SingleQubitMacroName,
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, LossDiVincenzoQuam
from quam_builder.builder.quantum_dots.build_qpu_stage1 import _BaseQpuBuilder
from quam_builder.builder.quantum_dots.build_qpu_stage2 import _LDQubitBuilder


class TunedX180Macro(X180Macro):
    """Instance-level custom X180 macro with gate-specific default pulse scaling."""

    default_amplitude_scale: float = 0.75


class DemoCZMacro(QubitPairMacro):
    """Type-level demo CZ macro.

    This is only an example placeholder to show how users replace the default
    fail-fast two-qubit gate placeholders with calibration-specific logic.
    """

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


def _plunger_ports(qubit_id: str) -> Dict[str, str]:
    return {"opx_output": f"#/wiring/qubits/{qubit_id}/p/opx_output"}


def _mw_drive_ports(qubit_id: str) -> Dict[str, str]:
    return {"opx_output": f"#/wiring/qubits/{qubit_id}/xy/opx_output"}


def _barrier_ports(pair_id: str) -> Dict[str, str]:
    return {"opx_output": f"#/wiring/qubit_pairs/{pair_id}/b/opx_output"}


def build_demo_machine() -> LossDiVincenzoQuam:
    """Build a small machine with 2 qubits and 1 qubit pair.

    This uses stage builders directly to avoid relying on external QuAM config
    migration state that can vary by local environment.
    """
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

    # Seed minimal reference pulse used by the demo program.
    # Only one pulse is needed — XYDriveMacro derives all rotations from it.
    for qubit in machine.qubits.values():
        if qubit.xy is None:
            continue
        qubit.xy.operations.setdefault(
            DrivePulseName.GAUSSIAN,
            pulses.GaussianPulse(length=64, amplitude=0.01, sigma=16),
        )

    wire_machine_macros(machine)
    return machine


def add_default_state_points(machine: LossDiVincenzoQuam) -> None:
    """Define canonical voltage points used by default state macros."""
    for qubit in machine.qubits.values():
        dot_id = qubit.quantum_dot.id
        qubit.with_step_point(VoltagePointName.INITIALIZE, {dot_id: 0.10}, duration=200)
        qubit.with_step_point(VoltagePointName.MEASURE, {dot_id: 0.15}, duration=200)
        qubit.with_step_point(VoltagePointName.EMPTY, {dot_id: 0.00}, duration=200)


def print_macro_summary(machine: LossDiVincenzoQuam, title: str) -> None:
    """Print macro class bindings for key components/macros."""
    q1 = machine.qubits["q1"]
    pair = machine.qubit_pairs["q1_q2"]
    print(f"\n=== {title} ===")
    print("q1 macros:", sorted(q1.macros.keys()))
    print("q1.initialize:", type(q1.macros[VoltagePointName.INITIALIZE]).__name__)
    print("q1.x180:", type(q1.macros[SingleQubitMacroName.X_180]).__name__)
    print("q1_q2.cz:", type(pair.macros[TwoQubitMacroName.CZ]).__name__)


def apply_macro_overrides(machine: LossDiVincenzoQuam) -> None:
    """Apply one instance-level and one component-type override."""
    wire_machine_macros(
        machine,
        macro_overrides={
            "component_types": {
                "LDQubit": {
                    "macros": {
                        VoltagePointName.INITIALIZE: {
                            "factory": InitializeStateMacro,
                            "params": {"ramp_duration": 64},
                        }
                    }
                },
                "LDQubitPair": {
                    "macros": {
                        TwoQubitMacroName.CZ: {"factory": DemoCZMacro},
                    }
                },
            },
            "instances": {
                "qubits.q1": {
                    "macros": {
                        SingleQubitMacroName.X_180: {"factory": TunedX180Macro},
                    }
                }
            },
        },
        strict=True,
    )


def build_program(machine: LossDiVincenzoQuam):
    """Build a QUA program using default and overridden macros."""
    q1 = machine.qubits["q1"]
    q2 = machine.qubits["q2"]
    pair = machine.qubit_pairs["q1_q2"]

    with qua.program() as prog:
        q1.initialize()
        q2.initialize()
        q1.x90()
        q1.x180()  # Uses TunedX180Macro after override.
        q2.empty()
        pair.cz()  # Uses DemoCZMacro after override.
        q1.measure()
        q2.measure()

    return prog


def main() -> None:
    machine = build_demo_machine()
    add_default_state_points(machine)
    print_macro_summary(machine, "Defaults")

    apply_macro_overrides(machine)
    print_macro_summary(machine, "After Overrides")

    _ = build_program(machine)
    print("\nBuilt QUA program successfully with wired default+override macros.")


if __name__ == "__main__":
    main()
