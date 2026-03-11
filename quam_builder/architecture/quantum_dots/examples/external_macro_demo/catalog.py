"""External macro catalog demonstrating lab-owned macro package pattern.

This module provides build_macro_overrides() for use with wire_machine_macros.
Custom macro classes use @quam_dataclass so they survive QuAM serialization.
"""

from __future__ import annotations

from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    InitializeStateMacro,
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


def build_macro_overrides() -> dict:
    """Build macro overrides dict for wire_machine_macros.

    Returns a mapping suitable for:
        wire_machine_macros(machine, macro_overrides=build_macro_overrides(), strict=True)

    Overrides QuantumDot.initialize with LabInitializeMacro.
    """
    return {
        "component_types": {
            "QuantumDot": {
                "macros": {
                    "initialize": {
                        "factory": LabInitializeMacro,
                        "params": {"lab_ramp_duration": 80},
                    }
                }
            },
        }
    }
