"""Example: macro wiring with catalog and instance overrides.

Demonstrates the recommended Python API for overriding macros:

1. ``wire_machine_macros(machine)`` -- wire all defaults.
2. ``TypeOverrideCatalog({LDQubit: {...}})`` -- override all qubits of a type.
3. ``instance_overrides={"qubits.q1": {...}}`` -- override one specific qubit.
4. ``DISABLED`` sentinel -- remove a macro from a component.
5. ``macro.update(...)`` -- calibrate a parameter on an already-wired override.

``TunedX180Macro`` subclasses ``X180Macro`` to expose a calibrated phase.
``BalancedDCz2QMacro`` (already in ``voltage_balanced_macros``) replaces
``cz``; it reads the pair's ``exchange`` point, which the tutorial machine
does not define, so ``add_exchange_point()`` adds it.

The script then prints the QUA program with ``generate_qua_script``.
"""

# pylint: disable=too-many-ancestors

from __future__ import annotations

from functools import partial
import numpy as np
from qm import generate_qua_script, qua

from quam_builder.architecture.quantum_dots.examples.tutorial_machine import build_tutorial_machine
from quam_builder.architecture.quantum_dots.macro_engine import DISABLED, wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.macro_catalog import TypeOverrideCatalog
from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import X180Macro
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import InitializeStateMacro
from quam_builder.architecture.quantum_dots.operations.voltage_balanced_macros import BalancedDCz2QMacro
from quam_builder.architecture.quantum_dots.operations.names import (
    SingleQubitMacroName,
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qubit_pair.ld_qubit_pair import LDQubitPair
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam

# ---------------------------------------------------------------------------
# Override an existing macro to expose a new calibration parameter
# ---------------------------------------------------------------------------


class TunedX180Macro(X180Macro):
    """X180 whose ``phase`` is a calibrated virtual-Z offset.

    ``apply`` adds ``self.phase`` to any phase passed at the call, then
    plays it with ``qubit.virtual_z`` before the pi pulse. Set the
    calibration with ``update(phase=...)`` after wiring. The value is
    stored on the macro and kept by ``machine.save``.
    """

    def update(self, *, phase: float | None = None, **kwargs) -> None:
        super().update(**kwargs)
        if phase is not None:
            self.phase = float(phase)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def print_macro_summary(machine: LossDiVincenzoQuam, title: str) -> None:
    """Print macro class bindings for key components/macros."""
    q1 = machine.qubits["q1"]
    q2 = machine.qubits["q2"]
    pair = machine.qubit_pairs["q1_q2"]
    print(f"\n=== {title} ===")
    print("q1.initialize:", type(q1.macros[VoltagePointName.INITIALIZE]).__name__)
    x180 = q1.macros[SingleQubitMacroName.X_180]
    print("q1.x180:", type(x180).__name__)
    print("q1.x180.phase:", x180.phase)
    print("q1_q2.cz:", type(pair.macros[TwoQubitMacroName.CZ]).__name__)
    print("q2.z180 present:", SingleQubitMacroName.Z_180 in q2.macros)


# ---------------------------------------------------------------------------
# Override wiring using the catalog API
# ---------------------------------------------------------------------------

def apply_macro_overrides(machine: LossDiVincenzoQuam) -> None:
    """Apply type-level and instance-level overrides.

    - ``TypeOverrideCatalog`` replaces macros on all instances of a type.
    - ``instance_overrides`` replaces macros on one specific component.
    """
    # build_tutorial_machine() already wired defaults. fill_only=False
    # replaces those macros; the default True only fills names that are missing.
    wire_machine_macros(
        machine,
        fill_only=False,
        catalogs=[
            TypeOverrideCatalog(
                {
                    LDQubit: {
                        SingleQubitMacroName.INITIALIZE: partial(
                            InitializeStateMacro,
                            ramp_duration=64,
                            hold_duration=1000
                        ),
                    },
                    LDQubitPair: {
                        TwoQubitMacroName.CZ: BalancedDCz2QMacro,
                    },
                }
            ),
        ],
        instance_overrides={
            "qubits.q1": {
                SingleQubitMacroName.X_180: TunedX180Macro,
            },
            "qubits.q2": {
                SingleQubitMacroName.Z_180: DISABLED,
            },
        },
    )


def add_exchange_point(machine: LossDiVincenzoQuam) -> None:
    """Register the ``exchange`` point ``BalancedDCz2QMacro`` ramps to.

    The macro reads this point as the positive exchange voltage and
    negates it for the other polarity. The tutorial machine does not
    define it.
    """
    pair = machine.qubit_pairs["q1_q2"]
    dot_ids = [dot.id for dot in pair.quantum_dot_pair.quantum_dots]
    pair.add_point(
        VoltagePointName.EXCHANGE,
        dict.fromkeys(dot_ids, 0.06),
        duration=1000,
    )


def build_program(machine: LossDiVincenzoQuam):
    """Build a QUA program using default and overridden macros."""
    q1 = machine.qubits["q1"]
    q2 = machine.qubits["q2"]
    pair = machine.qubit_pairs["q1_q2"]

    with qua.program() as prog:
        q1.initialize()
        q2.initialize()
        qua.align()
        q1.x180()
        q2.x180()
        qua.align()
        pair.cz()
        qua.align()
        q1.measure()
        q2.measure()

    return prog


def main() -> None:
    machine = build_tutorial_machine()
    print_macro_summary(machine, "Defaults")

    apply_macro_overrides(machine)
    print_macro_summary(machine, "After Overrides")

    # Calibrated phase for this qubit. Radians; virtual_z converts to QUA turns.
    machine.qubits["q1"].x180.update(phase=np.pi/4)
    print_macro_summary(machine, "After calibrating q1.x180.phase")

    add_exchange_point(machine)

    program = build_program(machine)
    print(
        "\n=== QUA program after catalog and instance overrides ===\n"
        + generate_qua_script(program)
    )


if __name__ == "__main__":
    main()
