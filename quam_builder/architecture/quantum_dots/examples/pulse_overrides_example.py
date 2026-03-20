"""Example: default pulse wiring and selective pulse overrides.

Demonstrates using the typed override API for pulse configuration:

1. ``wire_machine_macros(machine)`` — adds default ``gaussian`` pulse to XY drives.
2. ``component_overrides`` with ``pulse()`` helper — override all qubits of a type.
3. ``instance_overrides`` with ``pulse()`` helper — override one specific qubit.

Key imports for pulse overrides::

    from quam_builder.architecture.quantum_dots.macro_engine import (
        wire_machine_macros,
        pulse,       # build a pulse override entry
        overrides,   # group macros + pulses for one component
    )

Only one reference pulse (``gaussian``) is registered per qubit by default.
``XYDriveMacro`` scales amplitude for rotation angle and applies virtual-Z
for rotation axis, so all single-qubit gates derive from this single pulse.
"""

# pylint: disable=no-member  # WiringLineType enum members are runtime-only

# Components in this demo inherit from framework mixins with deep MRO.
# pylint: disable=too-many-ancestors

from __future__ import annotations

from typing import Dict

from qualang_tools.wirer.connectivity.wiring_spec import WiringLineType

from quam_builder.architecture.quantum_dots.components import QPU
from quam_builder.architecture.quantum_dots.macro_engine import (
    wire_machine_macros,
    pulse,
    overrides,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit
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
    """Build a small machine with 2 qubits and default pulse.

    ``wire_machine_macros()`` adds the default ``gaussian`` GaussianPulse
    to each qubit's XY drive.  All single-qubit gate macros derive from
    this single pulse.
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
        for pulse_name, p in sorted(ops.items()):
            cls_name = type(p).__name__
            length = getattr(p, "length", "?")
            amp = getattr(p, "amplitude", "?")
            axis = getattr(p, "axis_angle", "N/A")
            print(
                f"    {pulse_name:>10s}: {cls_name}(length={length}, amplitude={amp}, axis_angle={axis})"
            )


def apply_type_level_overrides(machine: LossDiVincenzoQuam) -> None:
    """Override gaussian pulse for ALL LDQubit instances.

    Uses ``component_overrides`` keyed by the ``LDQubit`` class.
    The ``pulse()`` helper constructs a validated pulse entry.

    Since all gate macros derive from this single pulse, the change
    affects x90, x180, y90, y180, etc. automatically.
    """
    wire_machine_macros(
        machine,
        component_overrides={
            LDQubit: overrides(
                pulses={
                    "gaussian": pulse("GaussianPulse", length=500, amplitude=0.3, sigma=83),
                }
            ),
        },
    )


def apply_instance_level_overrides(machine: LossDiVincenzoQuam) -> None:
    """Override gaussian on q1 only.

    Uses ``instance_overrides`` keyed by the component path string.
    Instance-level overrides take precedence over type-level overrides.
    """
    wire_machine_macros(
        machine,
        instance_overrides={
            "qubits.q1": overrides(
                pulses={
                    "gaussian": pulse("GaussianPulse", length=800, amplitude=0.15, sigma=133),
                }
            ),
        },
    )


def main() -> None:
    # 1. Build machine with default pulse
    machine = build_demo_machine()
    print_pulse_summary(machine, "Default Pulse")

    # 2. Apply type-level override: all qubits get a shorter gaussian
    apply_type_level_overrides(machine)
    print_pulse_summary(machine, "After Type-Level Override (gaussian on all LDQubits)")

    # 3. Apply instance-level override: q1 gets custom gaussian
    apply_instance_level_overrides(machine)
    print_pulse_summary(machine, "After Instance-Level Override (q1.gaussian custom)")


if __name__ == "__main__":
    main()
