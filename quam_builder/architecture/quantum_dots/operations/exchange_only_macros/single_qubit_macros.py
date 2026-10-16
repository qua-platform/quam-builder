"""Exchange-only single-qubit macro skeletons.

These macros target :class:`ExchangeOnlyQubit` components and are kept separate
from the LD implementations because EO control uses virtualized voltage axes
(``x_axis`` / ``z_axis`` on top of ``Jn`` / ``Jz``) rather than microwave
``xy`` channels and frame updates.
"""

from __future__ import annotations

from typing import ClassVar, Literal

import numpy as np

from quam.components.macro import QubitMacro
from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from quam_builder.architecture.quantum_dots.operations.exchange_only_macros.state_macros import (
    EO_STATE_MACROS,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    X_NEG_90_ALIAS,
    Y_NEG_90_ALIAS,
    SingleQubitMacroName,
    VoltagePointName,
)
from quam_builder.tools.qua_tools import VoltageLevelType

PointType = str | dict[str, VoltageLevelType]

__all__ = [
    "SINGLE_QUBIT_MACROS",
    "EOInitialize1QMacro",
    "EOMeasure1QMacro",
    "EOAxisDriveMacro",
    "EOExchange1QMacro", 
    "EOEmpty1QMacro", 
    "EOXMacro",
    "EOYMacro",
    "EOZMacro",
    "EOX180Macro",
    "EOX90Macro",
    "EOXNeg90Macro",
    "EOY180Macro",
    "EOY90Macro",
    "EOYNeg90Macro",
    "EOZ180Macro",
    "EOZ90Macro",
    "EOZNeg90Macro",
    "EOIdentityMacro",
]

@quam_dataclass
class EOEmpty1QMacro(QubitMacro):
    """Move an EO qubit to its empty configuration."""

    hold_duration: int | None = None

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, hold_duration: int | None = None, **kwargs):
        pass


@quam_dataclass
class EOExchange1QMacro(QubitMacro):
    """Execute an EO exchange pulse in the qubit control-axis frame."""

    ramp_duration: int = DEFAULTS.exchange.ramp_duration
    wait_duration: int = DEFAULTS.exchange.wait_duration

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        ramp_duration: int | None = None,
        wait_duration: int | None = None,
        **kwargs,
    ):
        pass


@quam_dataclass
class EOInitialize1QMacro(QubitMacro):
    """Initialize an EO qubit by coordinating its ``jn_pair`` and ``jz_pair``."""

    ramp_duration: int = DEFAULTS.state_macro.ramp_duration
    hold_duration: int = DEFAULTS.state_macro.hold_duration
    zero_duration: int = 16
    point_name: str = SingleQubitMacroName.INITIALIZE
    initialize_order: Literal["n_to_z", "z_to_n", "simultaneous"]

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self, 
        ramp_duration: int | None = None, 
        hold_duration: int | None = None, 
        zero_duration: int | None = None,
        point_name: str | None = None,
        initialize_order: Literal["n_to_z", "z_to_n", "simultaneous"] = "n_to_z",
        **kwargs
    ): 
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        hold = self.hold_duration if hold_duration is None else hold_duration
        zero_hold = self.zero_duration if zero_duration is None else zero_duration
        point = self.point_name if point_name is None else point_name

        # self.parent is the macro
        # macro.parent is the qubit
        # This macro is to be called from the qubit
        owner = self.parent.parent

        if initialize_order == "n_to_z": 
            owner.jn_pair.initialize(
                ramp, 
                hold, 
                zero_hold, 
                point,
            )
            owner.jz_pair.initialize(
                ramp, 
                hold, 
                zero_hold, 
                point,
            )

        if initialize_order == "z_to_n": 
            owner.jn_pair.initialize(
                ramp, 
                hold, 
                zero_hold, 
                point,
            )
            owner.jz_pair.initialize(
                ramp, 
                hold, 
                zero_hold, 
                point,
            )
        if initialize_order == "simultaneous": 
            gate_set = owner.voltage_sequence.gate_set
            jn_initialize_coordinate = gate_set.macros[point].voltages
            jz_initialize_coordinate = gate_set.macros[point].voltages 

            merged_dict = {
                k : jz_initialize_coordinate.get(k, 0.0) + jn_initialize_coordinate.get(k, 0.0) 
                for k in set(jn_initialize_coordinate) | set(jz_initialize_coordinate)
            }
            zero_dict = {k : 0.0 for k in merged_dict}
            owner.ramp_to_voltages(
                merged_dict, 
                ramp_duration = ramp, 
                hold_duration = hold, 
            )
            owner.ramp_to_voltages(
                zero_dict, 
                ramp_duration = ramp, 
                hold_duration = zero_hold,
            )


@quam_dataclass
class EOMeasure1QMacro(QubitMacro):
    """Measure an EO qubit using an EO-specific pair-sequencing protocol."""

    ramp_duration: int | None = DEFAULTS.state_macro.ramp_duration
    buffer_duration: int | None = DEFAULTS.state_macro.buffer_duration
    point: PointType = VoltagePointName.MEASURE.value

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        buffer_duration: int | None = None, 
        point: PointType | None = None, 
        ramp_duration: int | None = None,
        **kwargs, 
    ):
        buffer = self.buffer_duration if buffer_duration is None else buffer_duration
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        p = self.point if point is None else point

        owner = self.parent.parent

        # The Jz pair is measureable, as it separates the singlet from the triplet. 
        owner.jz_pair.measure(
            buffer_duration = buffer, 
            ramp_duration = ramp,
            point = p, 
        )

@quam_dataclass
class EOAxisDriveMacro(QubitMacro):
    """Base macro for EO single-qubit rotations in the control-axis frame."""

    reference_angle: float | None = None
    phase: float = 0.0

    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.X.value

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def update(
        self,
        *,
        amplitude_scale: float | None = None,
        duration: int | None = None,
        **kwargs,
    ) -> None:
        pass

    def apply(
        self,
        angle: float | None = None,
        amplitude_scale: float | None = None,
        duration: int | None = None,
        **kwargs,
    ):
        pass


@quam_dataclass
class EOXMacro(EOAxisDriveMacro):
    """Canonical EO X-axis rotation macro."""

    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.X.value
    reference_angle: float | None = None
    phase: float = 0.0


@quam_dataclass
class EOYMacro(EOAxisDriveMacro):
    """Canonical EO Y-axis rotation macro."""

    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.Y.value
    reference_angle: float | None = None
    phase: float = float(np.pi / 2)


@quam_dataclass
class EOZMacro(EOAxisDriveMacro):
    """Canonical EO Z-axis rotation macro."""

    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.Z.value
    reference_angle: float | None = None
    phase: float = float(np.pi)


@quam_dataclass
class EOX180Macro(EOAxisDriveMacro):
    """Apply a 180-degree rotation around the EO X axis."""

    axis_macro_name: str = SingleQubitMacroName.X.value
    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.X_180.value
    reference_angle: float = float(np.pi)
    phase: float = 0.0


@quam_dataclass
class EOX90Macro(EOAxisDriveMacro):
    """Apply a 90-degree rotation around the EO X axis."""

    axis_macro_name: str = SingleQubitMacroName.X.value
    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.X_90.value
    reference_angle: float = float(np.pi / 2)
    phase: float = 0.0


@quam_dataclass
class EOXNeg90Macro(EOAxisDriveMacro):
    """Apply a -90-degree rotation around the EO X axis."""

    axis_macro_name: str = SingleQubitMacroName.X.value
    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.X_NEG_90.value
    reference_angle: float = float(np.pi / 2)
    phase: float = float(np.pi)


@quam_dataclass
class EOY180Macro(EOAxisDriveMacro):
    """Apply a 180-degree rotation around the EO Y axis."""

    axis_macro_name: str = SingleQubitMacroName.Y.value
    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.Y_180.value
    reference_angle: float = float(np.pi)
    phase: float = float(np.pi / 2)


@quam_dataclass
class EOY90Macro(EOAxisDriveMacro):
    """Apply a 90-degree rotation around the EO Y axis."""

    axis_macro_name: str = SingleQubitMacroName.Y.value
    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.Y_90.value
    reference_angle: float = float(np.pi / 2)
    phase: float = float(np.pi / 2)


@quam_dataclass
class EOYNeg90Macro(EOAxisDriveMacro):
    """Apply a -90-degree rotation around the EO Y axis."""

    axis_macro_name: str = SingleQubitMacroName.Y.value
    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.Y_NEG_90.value
    reference_angle: float = float(np.pi / 2)
    phase: float = float(-np.pi / 2)


@quam_dataclass
class EOZ180Macro(EOAxisDriveMacro):
    """Apply a 180-degree rotation around the EO Z axis."""

    axis_macro_name: str = SingleQubitMacroName.Z.value
    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.Z_180.value
    reference_angle: float = float(np.pi)
    phase: float = 0.0


@quam_dataclass
class EOZ90Macro(EOAxisDriveMacro):
    """Apply a 90-degree rotation around the EO Z axis."""

    axis_macro_name: str = SingleQubitMacroName.Z.value
    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.Z_90.value
    reference_angle: float = float(np.pi / 2)
    phase: float = 0.0


@quam_dataclass
class EOZNeg90Macro(EOAxisDriveMacro):
    """Apply a -90-degree rotation around the EO Z axis."""

    axis_macro_name: str = SingleQubitMacroName.Z.value
    _axis_macro_name: ClassVar[str] = SingleQubitMacroName.Z_NEG_90.value
    reference_angle: float = float(np.pi / 2)
    phase: float = float(-np.pi / 2)


@quam_dataclass
class EOIdentityMacro(QubitMacro):
    """Identity operation placeholder for EO qubits."""

    duration: int = DEFAULTS.misc.identity_duration

    @property
    def inferred_duration(self) -> float:
        return self.duration * 1e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, duration: int | None = None, **kwargs):
        pass


SINGLE_QUBIT_MACROS = {
    **EO_STATE_MACROS,
    SingleQubitMacroName.XY_DRIVE.value: EOAxisDriveMacro,
    SingleQubitMacroName.X.value: EOXMacro,
    SingleQubitMacroName.Y.value: EOYMacro,
    SingleQubitMacroName.Z.value: EOZMacro,
    SingleQubitMacroName.X_180.value: EOX180Macro,
    SingleQubitMacroName.X_90.value: EOX90Macro,
    SingleQubitMacroName.X_NEG_90.value: EOXNeg90Macro,
    X_NEG_90_ALIAS: EOXNeg90Macro,
    SingleQubitMacroName.Y_180.value: EOY180Macro,
    SingleQubitMacroName.Y_90.value: EOY90Macro,
    SingleQubitMacroName.Y_NEG_90.value: EOYNeg90Macro,
    Y_NEG_90_ALIAS: EOYNeg90Macro,
    SingleQubitMacroName.Z_180.value: EOZ180Macro,
    SingleQubitMacroName.Z_90.value: EOZ90Macro,
    SingleQubitMacroName.Z_NEG_90.value: EOZNeg90Macro,
    SingleQubitMacroName.IDENTITY.value: EOIdentityMacro,
}
