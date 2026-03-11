"""Example: default pulse wiring and selective pulse overrides.

This script demonstrates:
1. Building a small quantum-dots machine with default pulses wired
   automatically by ``wire_machine_macros``.
2. Inspecting the default pulses on qubit XY drives and sensor dot resonators.
3. Applying type-level pulse overrides (all qubits of a type).
4. Applying instance-level pulse overrides (one specific qubit).
5. Disabling specific pulses via ``{enabled: false}``.

The pulse wiring system is integrated into ``wire_machine_macros()`` and
runs after macro wiring.  Default pulses are additive — only pulse names
not already present on a channel's ``operations`` dict are added.
"""

# pylint: disable=no-member  # WiringLineType enum members are runtime-only

# Components in this demo inherit from framework mixins with deep MRO.
# pylint: disable=too-many-ancestors

from __future__ import annotations

from typing import Dict

from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType

from quam_builder.architecture.quantum_dots.components import QPU
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
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
    """Build a small machine with 2 qubits and default pulses.

    ``wire_machine_macros()`` is called once during build and automatically
    adds default GaussianPulse rotations to each qubit's XY drive:
    x180, x90, y180, y90, -x90, -y90.
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
            "q1_q2": {WiringLineType.BARRIER_GATE.value: _barrier_ports("q1_q2")},
        },
    }
    machine = _BaseQpuBuilder(machine).build()
    machine = _LDQubitBuilder(machine).build()
    if getattr(machine, "qpu", None) is None:
        machine.qpu = QPU()

    # wire_machine_macros handles both macros AND pulses:
    wire_machine_macros(machine)
    return machine


def print_pulse_summary(machine: LossDiVincenzoQuam, title: str) -> None:
    """Print pulse operations for each qubit's XY drive."""
    print(f"\n=== {title} ===")
    for qubit_id, qubit in machine.qubits.items():
        xy = getattr(qubit, "xy", None)
        if xy is None:
            continue
        ops = getattr(xy, "operations", {})
        print(f"\n  {qubit_id}.xy.operations:")
        for pulse_name, pulse in sorted(ops.items()):
            cls_name = type(pulse).__name__
            length = getattr(pulse, "length", "?")
            amp = getattr(pulse, "amplitude", "?")
            axis = getattr(pulse, "axis_angle", "N/A")
            print(
                f"    {pulse_name:>6s}: {cls_name}(length={length}, amplitude={amp}, axis_angle={axis})"
            )


def apply_type_level_overrides(machine: LossDiVincenzoQuam) -> None:
    """Override x180 pulse for ALL LDQubit instances.

    This uses the ``component_types`` scope to set a shorter, stronger
    x180 Gaussian pulse on every qubit of type LDQubit.
    """
    wire_machine_macros(
        machine,
        macro_overrides={
            "component_types": {
                "LDQubit": {
                    "pulses": {
                        "x180": {
                            "type": "GaussianPulse",
                            "length": 500,
                            "amplitude": 0.3,
                            "sigma": 83,
                        },
                    }
                }
            },
        },
    )


def apply_instance_level_overrides(machine: LossDiVincenzoQuam) -> None:
    """Override x180 on q1 only, and disable -y90 on q2.

    Instance-level overrides take precedence over type-level overrides.
    Setting ``enabled: false`` removes the pulse from that qubit's operations.
    """
    wire_machine_macros(
        machine,
        macro_overrides={
            "instances": {
                "qubits.q1": {
                    "pulses": {
                        "x180": {
                            "type": "GaussianPulse",
                            "length": 800,
                            "amplitude": 0.15,
                            "sigma": 133,
                        },
                    }
                },
                "qubits.q2": {
                    "pulses": {
                        "-y90": {"enabled": False},
                    }
                },
            },
        },
    )


def main() -> None:
    # 1. Build machine with default pulses
    machine = build_demo_machine()
    print_pulse_summary(machine, "Default Pulses")

    # 2. Apply type-level override: all qubits get a shorter x180
    apply_type_level_overrides(machine)
    print_pulse_summary(machine, "After Type-Level Override (x180 on all LDQubits)")

    # 3. Apply instance-level override: q1 gets custom x180, q2 loses -y90
    apply_instance_level_overrides(machine)
    print_pulse_summary(machine, "After Instance-Level Override (q1.x180 + q2.-y90 disabled)")


if __name__ == "__main__":
    main()
