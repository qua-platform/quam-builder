"""Example: external macro package workflow.

This script demonstrates the external macro package pattern -- custom macros
in a separate package implementing the ``MacroCatalog`` protocol, passed to
``wire_machine_macros``.  Runs without QM hardware (no qm.open, qm.run, or machine.connect).

The key idea: keep lab-owned macro logic in a separate package so it
survives upstream quam-builder pulls.  The package exports a catalog object
for the ``catalogs`` kwarg of ``wire_machine_macros``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from qm import qua  # noqa: E402
from quam_builder.architecture.quantum_dots.examples.external_macro_demo.catalog import (  # noqa: E402
    LabMacroCatalog,
)
from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (  # noqa: E402
    build_tutorial_machine,
)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros  # noqa: E402


def main() -> None:
    """Build machine, wire macros with external catalog, and verify."""
    machine = build_tutorial_machine()

    wire_machine_macros(
        machine,
        catalogs=[LabMacroCatalog()],
    )

    q1 = machine.qubits["q1"]
    q2 = machine.qubits["q2"]
    pair = machine.quantum_dot_pairs["virtual_dot_1_virtual_dot_2_pair"]
    sensor_dot = machine.sensor_dots["virtual_sensor_1"]

    with qua.program() as _:
        q1.initialize()
        q2.initialize()
        pair.initialize()
        sensor_dot.macros["measure"].apply("readout")
        q1.measure()
        q2.measure()

    print("Built QUA program successfully with external macro catalog.")


if __name__ == "__main__":
    main()
