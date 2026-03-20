"""External macro catalog demonstrating lab-owned macro package pattern.

This module provides ``build_component_overrides()`` for use with
``wire_machine_macros``.  Custom macro classes use ``@quam_dataclass``
so they survive QuAM serialization.

Usage::

    from my_lab_macros.catalog import build_component_overrides
    from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros

    wire_machine_macros(
        machine,
        component_overrides=build_component_overrides(),
        strict=True,
    )
"""

from __future__ import annotations

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.components import QuantumDot
from quam_builder.architecture.quantum_dots.macro_engine import macro, overrides
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    InitializeStateMacro,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    SingleQubitMacroName,
)


@quam_dataclass
class LabInitializeMacro(InitializeStateMacro):
    """Custom initialize macro with lab-specific ramp duration.

    Demonstrates parametrization via an extra serializable field.
    """

    lab_ramp_duration: int = 64

    def apply(
        self,
        ramp_duration: int | None = None,
        hold_duration: int | None = None,
        **kwargs,
    ):
        """Ramp to initialize point using lab_ramp_duration when ramp_duration not specified."""
        ramp = ramp_duration if ramp_duration is not None else self.lab_ramp_duration
        return super().apply(ramp_duration=ramp, hold_duration=hold_duration, **kwargs)


def build_component_overrides() -> dict:
    """Build component_overrides for wire_machine_macros.

    Returns a mapping keyed by component class, suitable for::

        wire_machine_macros(
            machine,
            component_overrides=build_component_overrides(),
            strict=True,
        )

    Overrides QuantumDot.initialize with LabInitializeMacro.
    """
    return {
        QuantumDot: overrides(
            macros={
                SingleQubitMacroName.INITIALIZE: macro(
                    LabInitializeMacro,
                    lab_ramp_duration=80,
                ),
            }
        ),
    }
