"""Example: external macro package workflow.

This script demonstrates the external macro package pattern — custom macros
in a separate package, imported and passed to wire_machine_macros.
Runs without QM hardware (no qm.open, qm.run, or machine.connect).

Uses the tutorial machine with QuantumDot, QuantumDotPair, and SensorDot
component types. Passes build_macro_overrides() from external_macro_demo
to wire_machine_macros so that lab-owned macro logic survives upstream pulls.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as: python quam_builder/.../external_macro_package_example.py
_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from qm import qua  # noqa: E402
from quam_builder.architecture.quantum_dots.examples.external_macro_demo.catalog import (  # noqa: E402
    build_macro_overrides,
)
from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (  # noqa: E402
    build_tutorial_machine,
)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros  # noqa: E402


def main() -> None:
    """Build machine, wire macros with external overrides, and verify."""
    machine = build_tutorial_machine()
    wire_machine_macros(
        machine,
        macro_overrides=build_macro_overrides(),
        strict=True,
    )

    q1 = machine.qubits["Q1"]
    q2 = machine.qubits["Q2"]
    pair = machine.quantum_dot_pairs["dot1_dot2_pair"]
    sensor_dot = machine.sensor_dots["virtual_sensor_1"]

    with qua.program() as _:
        q1.initialize()
        q2.initialize()
        pair.initialize()
        sensor_dot.macros["measure"].apply("readout")
        q1.measure()
        q2.measure()

    print("Built QUA program successfully with external macro overrides.")


if __name__ == "__main__":
    main()
