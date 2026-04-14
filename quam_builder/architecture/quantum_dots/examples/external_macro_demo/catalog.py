"""External macro catalog demonstrating lab-owned macro package pattern.

This module implements the ``MacroCatalog`` protocol for use with
``wire_machine_macros``.  Custom macro classes use ``@quam_dataclass``
so they survive QuAM serialization.

Usage::

    from my_lab_macros.catalog import LabMacroCatalog
    from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros

    wire_machine_macros(machine, catalogs=[LabMacroCatalog()])
"""

from __future__ import annotations

from functools import partial
from typing import Any

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.operations.macro_catalog import (
    MacroFactoryMap,
)
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
        **kwargs: Any,
    ) -> None:
        """Ramp to initialize point using lab_ramp_duration when ramp_duration not specified."""
        ramp = ramp_duration if ramp_duration is not None else self.lab_ramp_duration
        return super().apply(ramp_duration=ramp, hold_duration=hold_duration, **kwargs)


class LabMacroCatalog:
    """Lab-owned macro catalog implementing the MacroCatalog protocol.

    Override QuantumDot.initialize with LabInitializeMacro.
    """

    priority = 200

    def get_factories(self, component_type: type) -> MacroFactoryMap:
        """Return lab-specific factories for *component_type*."""
        from quam_builder.architecture.quantum_dots.components import QuantumDot

        if issubclass(component_type, QuantumDot):
            return {
                SingleQubitMacroName.INITIALIZE: partial(
                    LabInitializeMacro,
                    lab_ramp_duration=80,
                ),
            }
        return {}
