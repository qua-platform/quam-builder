"""Example: external macro package workflow.

This script demonstrates the external macro package pattern -- custom macros
in a separate package implementing the ``MacroCatalog`` protocol, passed to
``wire_machine_macros``.  Runs without QM hardware (no qm.open, qm.run, or machine.connect).

The key idea: keep lab-owned macro logic in a separate package so it
survives upstream quam-builder pulls.  The package exports a catalog object
for the ``catalogs`` kwarg of ``wire_machine_macros``.
"""

from __future__ import annotations

from qm import qua

from quam_builder.architecture.quantum_dots.examples.external_macro_demo.catalog import (
    LabMacroCatalog,
)
from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.names import VoltagePointName


def _initialize_class(component) -> str:
    name = VoltagePointName.INITIALIZE.value
    if name not in component.macros:
        return "absent"
    return type(component.macros[name]).__name__


def main() -> None:
    """Build machine, wire macros with external catalog, and verify."""
    machine = build_tutorial_machine()
    dot = machine.quantum_dots["virtual_dot_1"]
    sensor = machine.sensor_dots["virtual_sensor_1"]
    print("Before catalog:")
    print("  virtual_dot_1.initialize:", _initialize_class(dot))
    print("  virtual_sensor_1.initialize:", _initialize_class(sensor))

    # The tutorial machine is already wired. fill_only=False lets the lab
    # catalog replace QuantumDot.initialize. SensorDot is a QuantumDot, so
    # the same factory is applied there too.
    wire_machine_macros(
        machine,
        fill_only=False,
        catalogs=[LabMacroCatalog()],
    )

    lab_initialize = dot.macros[VoltagePointName.INITIALIZE.value]
    print("After catalog:")
    print("  virtual_dot_1.initialize:", type(lab_initialize).__name__)
    print("  lab_ramp_duration:", lab_initialize.lab_ramp_duration)
    print("  virtual_sensor_1.initialize:", _initialize_class(sensor))

    # Tutorial voltage points live on the qubits and dot pairs. The lab
    # macro ramps this dot, so it needs its own initialize point.
    dot.add_point(VoltagePointName.INITIALIZE, {dot.id: 0.10}, duration=200)

    with qua.program() as _:
        dot.initialize()

    print("Built QUA program successfully with external macro catalog.")


if __name__ == "__main__":
    main()
