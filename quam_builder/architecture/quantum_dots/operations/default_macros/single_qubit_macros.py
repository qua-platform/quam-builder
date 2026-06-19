"""Single-qubit default macros for quantum-dot qubits.

Pulse family switching
----------------------
All single-qubit XY rotations are parameterised by a **pulse family**
(``"gaussian"``, ``"square"``, ``"kaiser"``, ``"hermite"``, or ``"drag"``).  The active family is
stored in ``XYDriveMacro.pulse_family`` and determines which operation
from ``qubit.xy.operations`` is played.  Operations follow the naming
convention ``{family}_{gate}`` (e.g. ``"kaiser_x180"``).

Changing ``machine.pulse_family`` (and propagating via
``machine.set_pulse_family()``) switches **all** macros simultaneously.

Rescaling philosophy
--------------------
The ``XYDriveMacro`` rescales only **amplitude** and **phase** at the
macro level:

* **Amplitude** is scaled proportionally to the requested rotation angle
  relative to ``reference_angle`` (default π).
* **Phase** selects the rotation axis via a virtual-Z frame rotation
  (0 → X, π/2 → Y, arbitrary → any XY axis).

The pulse is **never time-stretched** via QUA's ``play(duration=…)``
parameter, because arbitrary waveforms (Gaussian, Kaiser) have internal
shape parameters defined in absolute samples.  By always playing at the
pulse's native ``length``, the macro guarantees the waveform shape is
self-consistent.

For experiments that require sweeping pulse duration (e.g. time-Rabi),
users should define a custom macro that explicitly accepts the
shape/length trade-off, or register multiple pulses with different
length parameters.
"""

# Framework macro base classes introduce deep inheritance chains by design.
# pylint: disable=too-many-ancestors

from __future__ import annotations

import dataclasses
import math
from typing import ClassVar

import numpy as np

from qm.qua import wait
from quam.components.macro import QubitMacro
from quam.components.quantum_components.qubit import qua
from quam.core import quam_dataclass
from quam.core.macro import QuamMacro
from virtual_qpu import pulse

from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    EmptyStateMacro,
    InitializeStateMacro,
    MeasurePSBPairMacro,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    X_NEG_90_ALIAS,
    Y_NEG_90_ALIAS,
    DrivePulseName,
    SingleQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from quam_builder.tools.qua_tools import CLOCK_CYCLE_NS, is_qua_type

__all__ = [
    "SINGLE_QUBIT_MACROS",
    "Initialize1QMacro",
    "Measure1QMacro",
    "Empty1QMacro",
    "XYDriveMacro",
    "XMacro",
    "YMacro",
    "ZMacro",
    "X180Macro",
    "X90Macro",
    "XNeg90Macro",
    "Y180Macro",
    "Y90Macro",
    "YNeg90Macro",
    "Z180Macro",
    "Z90Macro",
    "ZNeg90Macro",
    "IdentityMacro",
]


def _quantize_ns(duration_ns: float) -> int:
    """Quantize nanoseconds to OPX 4 ns clock boundaries."""
    return max(int(round(duration_ns / 4.0)) * 4, 0)


def _compose_phase(base_phase: float, extra_phase: float | None) -> float:
    """Combine phase offsets across macro layers."""
    if extra_phase is None:
        return base_phase
    return base_phase + extra_phase


def _compose_amplitude_scale(
    base_scale: float,
    extra_scale: float | None,
) -> float | None:
    """Combine amplitude scales across macro layers.

    Returns ``None`` only when the composition is an identity scaling.
    """
    scale = base_scale if extra_scale is None else base_scale * extra_scale
    if extra_scale is None and math.isclose(scale, 1.0):
        return None
    return scale


def _resolve_qubit_pair(qubit):
    """Resolve the LDQubitPair for a qubit via preferred_readout_quantum_dot.

    Iterates ``machine.qubit_pairs`` to find a pair where one member is
    *qubit* and the other member's quantum dot matches
    ``preferred_readout_quantum_dot``.

    Raises:
        ValueError: If preferred_readout_quantum_dot is not set or pair not found.
    """
    preferred_dot_id = getattr(qubit, "preferred_readout_quantum_dot", None)
    if preferred_dot_id is None:
        raise ValueError(
            f"Qubit '{qubit.id}' has no preferred_readout_quantum_dot set."
        )
    machine = qubit.machine
    for pair in machine.qubit_pairs.values():
        qc, qt = pair.qubit_control, pair.qubit_target
        if qc is qubit and qt.quantum_dot.id == preferred_dot_id:
            return pair
        if qt is qubit and qc.quantum_dot.id == preferred_dot_id:
            return pair
    raise ValueError(
        f"No QubitPair found for qubit '{qubit.id}' with "
        f"preferred_readout_quantum_dot '{preferred_dot_id}'."
    )


def _state_macro_field_names(state_macro_cls: type) -> frozenset[str]:
    """Dataclass field names on *state_macro_cls* excluding QuamMacro base fields."""
    base = {f.name for f in dataclasses.fields(QuamMacro)}
    return frozenset(f.name for f in dataclasses.fields(state_macro_cls)) - base


@quam_dataclass
class Initialize1QMacro(QubitMacro):
    """Initialize qubit by delegating to the QuantumDotPair's initialize macro."""

    _CANONICAL_MACRO_NAME = "initialize"

    def _resolve_canonical_macro(self):
        pair = _resolve_qubit_pair(self.qubit)
        return pair.macros[self._CANONICAL_MACRO_NAME]

    @property
    def inferred_duration(self) -> float | None:
        try:
            return self._resolve_canonical_macro().inferred_duration
        except (ValueError, KeyError):
            return None

    def update(self, **kwargs) -> None:
        self._resolve_canonical_macro().update(**kwargs)

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        # Let qubit.initialize() default to driving/conditioning on itself when
        # the underlying initialize macro supports heralded arguments.
        if kwargs.get("qubit_name") is None:
            kwargs["qubit_name"] = self.qubit.name
        return self._resolve_canonical_macro().apply(**kwargs)

    def __getattr__(self, name):
        field_names = _state_macro_field_names(InitializeStateMacro)
        if name in field_names:
            return getattr(self._resolve_canonical_macro(), name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name, value):
        try:
            field_names = _state_macro_field_names(InitializeStateMacro)
        except TypeError:
            field_names = frozenset()
        if name in field_names:
            setattr(self._resolve_canonical_macro(), name, value)
            return
        super().__setattr__(name, value)


@quam_dataclass
class Measure1QMacro(QubitMacro):
    """PSB measure macro for a single qubit.

    Navigates from the qubit to its preferred readout quantum dot,
    finds the corresponding QuantumDotPair, and delegates to the
    pair's measure macro which performs the full PSB readout chain.
    """

    _CANONICAL_MACRO_NAME = "measure"

    def _resolve_canonical_macro(self):
        pair = _resolve_qubit_pair(self.qubit)
        return pair.macros[self._CANONICAL_MACRO_NAME]

    @property
    def inferred_duration(self) -> float | None:
        try:
            return self._resolve_canonical_macro().inferred_duration
        except (ValueError, KeyError):
            return None

    def update(self, **kwargs) -> None:
        self._resolve_canonical_macro().update(**kwargs)

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        return self._resolve_canonical_macro().apply(**kwargs)

    def __getattr__(self, name):
        field_names = _state_macro_field_names(MeasurePSBPairMacro)
        if name in field_names:
            return getattr(self._resolve_canonical_macro(), name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name, value):
        try:
            field_names = _state_macro_field_names(MeasurePSBPairMacro)
        except TypeError:
            field_names = frozenset()
        if name in field_names:
            setattr(self._resolve_canonical_macro(), name, value)
            return
        super().__setattr__(name, value)


@quam_dataclass
class Empty1QMacro(QubitMacro):
    """Move qubit to empty by delegating to the QuantumDotPair's empty macro."""

    _CANONICAL_MACRO_NAME = "empty"

    def _resolve_canonical_macro(self):
        pair = _resolve_qubit_pair(self.qubit)
        return pair.macros[self._CANONICAL_MACRO_NAME]

    @property
    def inferred_duration(self) -> float | None:
        try:
            return self._resolve_canonical_macro().inferred_duration
        except (ValueError, KeyError):
            return None

    def update(self, **kwargs) -> None:
        self._resolve_canonical_macro().update(**kwargs)

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        return self._resolve_canonical_macro().apply(**kwargs)

    def __getattr__(self, name):
        field_names = _state_macro_field_names(EmptyStateMacro)
        if name in field_names:
            return getattr(self._resolve_canonical_macro(), name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name, value):
        try:
            field_names = _state_macro_field_names(EmptyStateMacro)
        except TypeError:
            field_names = frozenset()
        if name in field_names:
            setattr(self._resolve_canonical_macro(), name, value)
            return
        super().__setattr__(name, value)


@quam_dataclass
class XYDriveMacro(QubitMacro):
    """Base macro for XY-plane rotations with switchable pulse families.

    The active pulse envelope is determined by ``pulse_family`` combined
    with a per-subclass ``_gate_suffix``.  Changing ``pulse_family``
    (e.g. from ``"gaussian"`` to ``"kaiser"``) switches the envelope
    used by all XY macros simultaneously.
    """

    pulse_family: str = DrivePulseName.GAUSSIAN.value
    reference_angle: float = None
    phase: float = None

    _gate_suffix: ClassVar[str] = "_x90"
    _reference_gate_suffix: ClassVar[str] = "_x90"

    @property
    def pulse_name(self) -> str:
        """Operation name resolved from the active family and gate suffix."""
        return f"{self.pulse_family}{self._gate_suffix}"

    @property
    def reference_pulse_name(self) -> str:
        """Reference (x90) operation name for the active family."""
        return f"{self.pulse_family}{self._reference_gate_suffix}"

    @property
    def pulse(self):
        """Return the pulse object backing this macro's XY rotations."""
        return self.qubit.xy.operations[self.reference_pulse_name]

    @property
    def pi_pulse(self):
        """Return the pi pulse (x180) object for the active family."""
        return self.qubit.xy.operations[f"{self.pulse_family}_x180"]

    @property
    def inferred_duration(self) -> float | None:
        return self.pulse.length

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def update(
        self,
        *,
        pi_amplitude: float | None = None,
        amplitude_scale: float | None = None,
        duration: int | None = None,
        frequency: float | None = None,
        frequency_offset: float | None = None,
    ) -> None:
        """Persistently update calibrated pulse parameters.

        Changes are applied to the QuAM state objects directly and are
        captured by subsequent serialisation (``machine.save``).

        Args:
            pi_amplitude: Set the x180 pulse amplitude to this value and
                the x90 pulse amplitude to half this value.
            amplitude_scale: Multiply the current amplitudes of both
                pulses by this factor.  Mutually exclusive with
                *pi_amplitude*.
            duration: Set the reference pulse length in **nanoseconds**
                (quantised to 4 ns).  For Gaussian pulses, sigma
                auto-scales via ``sigma_ratio``.
            frequency: Set ``qubit.larmor_frequency`` to this absolute
                value (Hz).  Mutually exclusive with *frequency_offset*.
            frequency_offset: Add this offset (Hz) to the current
                ``qubit.larmor_frequency``.
        """
        if pi_amplitude is not None and amplitude_scale is not None:
            raise ValueError("pi_amplitude and amplitude_scale are mutually exclusive")

        if pi_amplitude is not None:
            self.pulse.amplitude = pi_amplitude / 2
            self.pi_pulse.amplitude = pi_amplitude

        if amplitude_scale is not None:
            self.pulse.amplitude = self.pulse.amplitude * amplitude_scale
            self.pi_pulse.amplitude = self.pi_pulse.amplitude * amplitude_scale

        if duration is not None:
            self.pulse.length = duration
            self.pi_pulse.length = duration

            if hasattr(self.pulse, "sigma_ratio"):
                self.pulse.sigma = duration * self.pulse.sigma_ratio
                self.pi_pulse.sigma = duration * self.pi_pulse.sigma_ratio

        if frequency is not None:
            self.qubit.larmor_frequency = float(frequency)

        elif frequency_offset is not None:
            self.qubit.larmor_frequency = float(
                self.qubit.larmor_frequency + frequency_offset
            )

    def apply(
            self,
            phase: float = 0.0,
            amplitude_scale: float | None = None,
            duration=None,
            **kwargs,
    ):
        phase += self.phase

        if not math.isclose(phase, 0.0):
            self.qubit.virtual_z(phase)
        self.qubit.xy.play(
            pulse_name=self.pulse_name,
            amplitude_scale=amplitude_scale,
            duration=duration
        )


@quam_dataclass
class XMacro(XYDriveMacro):
    """Canonical X-axis rotation macro."""

    _gate_suffix: ClassVar[str] = "_x90"

    reference_angle: float = None
    phase: float = 0.0


@quam_dataclass
class YMacro(XYDriveMacro):
    """Canonical Y-axis rotation macro."""

    _gate_suffix: ClassVar[str] = "_y90"

    reference_angle: float = None
    phase: float = -np.pi


@quam_dataclass
class ZMacro(QubitMacro):
    """Canonical virtual-Z rotation macro."""

    default_angle: float = float(np.pi)

    @property
    def inferred_duration(self) -> float:
        """Virtual-Z is frame-only and therefore has zero duration."""
        return 0.0

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, angle: float | None = None, **kwargs):
        """Apply virtual-Z rotation for requested angle."""
        target_angle = self.default_angle if angle is None else float(angle)
        self.qubit.virtual_z(target_angle)


@quam_dataclass
class X180Macro(XYDriveMacro):
    """Apply 180-degree rotation around X axis via the dedicated pi pulse."""

    _gate_suffix: ClassVar[str] = "_x180"

    axis_macro_name: str = SingleQubitMacroName.X.value
    reference_angle: float = float(np.pi)
    phase: float = 0.0


@quam_dataclass
class X90Macro(XYDriveMacro):
    """Apply 90-degree rotation around X axis."""

    _gate_suffix: ClassVar[str] = "_x90"

    axis_macro_name: str = SingleQubitMacroName.X.value
    reference_angle: float = float(np.pi / 2)
    phase: float = 0.0


@quam_dataclass
class XNeg90Macro(XYDriveMacro):
    """Apply -90-degree rotation around X axis via dedicated pulse with axis_angle=pi."""

    _gate_suffix: ClassVar[str] = "_x_neg90"

    axis_macro_name: str = SingleQubitMacroName.X.value
    reference_angle: float = float(np.pi / 2)
    phase: float = 0.0


@quam_dataclass
class Y180Macro(XYDriveMacro):
    """Apply 180-degree rotation around Y axis via dedicated pulse with axis_angle=pi/2."""

    _gate_suffix: ClassVar[str] = "_y180"

    axis_macro_name: str = SingleQubitMacroName.Y.value
    reference_angle: float = float(np.pi)
    phase: float = 0.0


@quam_dataclass
class Y90Macro(XYDriveMacro):
    """Apply 90-degree rotation around Y axis via dedicated pulse with axis_angle=pi/2."""

    _gate_suffix: ClassVar[str] = "_y90"

    axis_macro_name: str = SingleQubitMacroName.Y.value
    reference_angle: float = float(np.pi / 2)
    phase: float = 0.0


@quam_dataclass
class YNeg90Macro(XYDriveMacro):
    """Apply -90-degree rotation around Y axis via dedicated pulse with axis_angle=-pi/2."""

    _gate_suffix: ClassVar[str] = "_y_neg90"

    axis_macro_name: str = SingleQubitMacroName.Y.value
    reference_angle: float = float(np.pi / 2)
    phase: float = 0.0


@quam_dataclass
class Z180Macro(ZMacro):
    """Apply virtual 180-degree Z rotation via canonical `z` macro."""
    axis_macro_name: str = SingleQubitMacroName.Z.value
    default_angle: float = float(np.pi)


@quam_dataclass
class Z90Macro(ZMacro):
    """Apply virtual 90-degree Z rotation via canonical `z` macro."""
    axis_macro_name: str = SingleQubitMacroName.Z.value
    default_angle = float(np.pi / 2)


@quam_dataclass
class ZNeg90Macro(ZMacro):
    """Apply virtual -90-degree Z rotation via canonical `z` macro."""
    axis_macro_name: str = SingleQubitMacroName.Z.value
    default_angle = float(-np.pi / 2)

@quam_dataclass
class IdentityMacro(QubitMacro):
    """Identity operation implemented as wait."""

    duration: int = DEFAULTS.misc.identity_duration

    @property
    def inferred_duration(self) -> float:
        """Return configured wait duration in seconds."""
        return self.duration * 1e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, duration: int | None = None, **kwargs):
        self.qubit.idle(duration=duration)


SINGLE_QUBIT_MACROS = {
    VoltagePointName.INITIALIZE.value: Initialize1QMacro,
    VoltagePointName.MEASURE.value: Measure1QMacro,
    VoltagePointName.EMPTY.value: Empty1QMacro,
    SingleQubitMacroName.XY_DRIVE.value: XYDriveMacro,
    SingleQubitMacroName.X.value: XMacro,
    SingleQubitMacroName.Y.value: YMacro,
    SingleQubitMacroName.Z.value: ZMacro,
    SingleQubitMacroName.X_180.value: X180Macro,
    SingleQubitMacroName.X_90.value: X90Macro,
    SingleQubitMacroName.X_NEG_90.value: XNeg90Macro,
    X_NEG_90_ALIAS: XNeg90Macro,
    SingleQubitMacroName.Y_180.value: Y180Macro,
    SingleQubitMacroName.Y_90.value: Y90Macro,
    SingleQubitMacroName.Y_NEG_90.value: YNeg90Macro,
    Y_NEG_90_ALIAS: YNeg90Macro,
    SingleQubitMacroName.Z_180.value: Z180Macro,
    SingleQubitMacroName.Z_90.value: Z90Macro,
    SingleQubitMacroName.Z_NEG_90.value: ZNeg90Macro,
    SingleQubitMacroName.IDENTITY.value: IdentityMacro,
}
# Default single-qubit macro factories for ``LDQubit`` components.
