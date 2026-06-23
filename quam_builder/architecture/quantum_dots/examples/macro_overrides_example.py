"""Example: macro wiring with catalog and instance overrides.

Demonstrates the recommended Python API for overriding macros:

1. ``wire_machine_macros(machine)`` -- wire all defaults.
2. ``TypeOverrideCatalog({LDQubit: {...}})`` -- override all qubits of a type.
3. ``instance_overrides={"qubits.q1": {...}}`` -- override one specific qubit.
4. ``DISABLED`` sentinel -- remove a macro from a component.
"""

# pylint: disable=too-many-ancestors

from __future__ import annotations

from functools import partial

from qm import qua
from quam.components.macro import QubitPairMacro

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.macro_catalog import (
    TypeOverrideCatalog,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    X180Macro,
)
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    InitializeStateMacro,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    SingleQubitMacroName,
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qubit_pair.ld_qubit_pair import LDQubitPair
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam

# ---------------------------------------------------------------------------
# Custom macro classes (users would define these in their lab package)
# ---------------------------------------------------------------------------


class TunedX180Macro(X180Macro):
    """Lab-calibrated X180 macro for a specific qubit."""

    pass


class DemoCZMacro(QubitPairMacro):
    """Placeholder CZ gate showing how users replace default 2Q stubs."""

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def print_macro_summary(machine: LossDiVincenzoQuam, title: str) -> None:
    """Print macro class bindings for key components/macros."""
    q1 = machine.qubits["q1"]
    pair = machine.qubit_pairs["q1_q2"]
    print(f"\n=== {title} ===")
    print("q1 macros:", sorted(q1.macros.keys()))
    print("q1.initialize:", type(q1.macros[VoltagePointName.INITIALIZE]).__name__)
    print("q1.x180:", type(q1.macros[SingleQubitMacroName.X_180]).__name__)
    print("q1_q2.cz:", type(pair.macros[TwoQubitMacroName.CZ]).__name__)


# ---------------------------------------------------------------------------
# Override wiring using the catalog API
# ---------------------------------------------------------------------------


def apply_macro_overrides(machine: LossDiVincenzoQuam) -> None:
    """Apply type-level and instance-level overrides.

    - ``TypeOverrideCatalog`` replaces macros on all instances of a type.
    - ``instance_overrides`` replaces macros on one specific component.
    """
    wire_machine_macros(
        machine,
        catalogs=[
            TypeOverrideCatalog(
                {
                    LDQubit: {
                        SingleQubitMacroName.INITIALIZE: partial(
                            InitializeStateMacro,
                            ramp_duration=64,
                        ),
                    },
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


def build_program(machine: LossDiVincenzoQuam):
    """Build a QUA program using default and overridden macros."""
    q1 = machine.qubits["q1"]
    q2 = machine.qubits["q2"]
    pair = machine.qubit_pairs["q1_q2"]

    with qua.program() as prog:
        q1.initialize()
        q2.initialize()
        q1.x90()
        q1.x180()
        q2.empty()
        pair.cz()
        q1.measure()
        q2.measure()

    return prog


def main() -> None:
    machine = build_tutorial_machine()
    print_macro_summary(machine, "Defaults")

    apply_macro_overrides(machine)
    print_macro_summary(machine, "After Overrides")

    _ = build_program(machine)
    print("\nBuilt QUA program successfully with wired default+override macros.")


if __name__ == "__main__":
    main()
