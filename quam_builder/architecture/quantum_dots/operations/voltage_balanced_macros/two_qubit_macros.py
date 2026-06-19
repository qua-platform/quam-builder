"""Voltage-balanced two-qubit macros for LD qubit pairs."""

# pylint: disable=too-many-ancestors
from __future__ import annotations

from typing import Any, Dict, Optional

from qm import qua
from quam.components.macro import QubitPairMacro
from quam.core import quam_dataclass

from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    SingleQubitMacroName,
    VoltagePointName,
)

from quam_builder.architecture.quantum_dots.operations.voltage_balanced_macros.state_macros import (
    _point_voltages,
    _zero_voltages,
)

__all__ = ["BalancedCz2QMacro", "BalancedDCz2QMacro", "BalancedCROTMacro"]


@quam_dataclass
class BalancedCz2QMacro(QubitPairMacro):
    """Voltage-balanced exchange pulse.

    Shape (per channel):

        0 ──step──▶ -V_ex ──hold(T)── -V_ex
        ──step──▶ +V_ex ──hold(T)── +V_ex ──step──▶ 0

    ``V_ex`` is the voltage stored at the pair's ``exchange`` point (the
    positive-polarity barrier configuration). The negative-polarity leg
    uses an element-wise negation of that point. Equal hold times at the
    two polarities give a zero net integrated voltage on every channel.
    """

    point: str = VoltagePointName.EXCHANGE.value
    wait_duration: int = DEFAULTS.exchange.wait_duration
    ramp_duration: int = DEFAULTS.exchange.ramp_duration

    phase_shift_control: float = 0.0
    phase_shift_target: float = 0.0

    exchange_decay_model: Optional[Dict[str, Any]] = None
    """Fitted T_2π(V) model from swap oscillations.

    Serialisable dict with a ``"type"`` key that identifies the function::

        {
            "type": "polynomial",
            "coeffs": [c_n, ..., c_0],   # highest-degree-first
            "degree": int,
        }

    ``None`` if not yet calibrated (run ``18a_swap_oscillations``).
    """

    @property
    def inferred_duration(self) -> float | None:
        return 2 * self.wait_duration * 1e-9 + 4 * self.ramp_duration * 1e-9

    def t_2pi(self, amplitude: float) -> float:
        """Evaluate the calibrated T_2π(V) model (ns).

        Requires :attr:`exchange_decay_model` to have been populated by
        node ``18a_swap_oscillations``.

        Parameters
        ----------
        amplitude : float
            Barrier gate voltage (V).

        Returns
        -------
        float
            Full 2π swap oscillation period in nanoseconds.
        """
        m = self.exchange_decay_model
        if m is None:
            raise ValueError(
                "T_2π model not calibrated.  Run 18a_swap_oscillations first."
            )
        model_type = m.get("type", "polynomial")
        if model_type == "polynomial":
            result = 0.0
            for c in m["coeffs"]:
                result = result * amplitude + c
            return result
        raise ValueError(f"Unknown exchange_decay_model type: {model_type!r}")

    def t_cz(self, amplitude: float) -> float:
        """Return T_2π(V) / 2 — the CZ wait_duration for a π conditional phase.

        Parameters
        ----------
        amplitude : float
            Barrier gate voltage (V).

        Returns
        -------
        float
            Half-period in nanoseconds (round to 4 ns for QUA clock).
        """
        return self.t_2pi(amplitude) / 2.0

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def update(
        self,
        *,
        wait_duration: int | None = None,
        point: str | None = None,
        ramp_duration: int | None = None,
        phase_shift_control: float | None = None,
        phase_shift_target: float | None = None,
        exchange_decay_model: dict | None = None,
    ) -> None:
        if wait_duration is not None:
            self.wait_duration = wait_duration
        if point is not None:
            self.point = point
        if ramp_duration is not None:
            self.ramp_duration = ramp_duration
        if phase_shift_control is not None:
            self.phase_shift_control = phase_shift_control
        if phase_shift_target is not None:
            self.phase_shift_target = phase_shift_target
        if exchange_decay_model is not None:
            self.exchange_decay_model = exchange_decay_model

    def apply(
        self,
        wait_duration: int | None = None,
        ramp_duration: int | None = None,
        point: str | None = None,
        phase_shift_control: float | None = None,
        phase_shift_target: float | None = None,
        **kwargs,
    ):
        wait = self.wait_duration if wait_duration is None else wait_duration
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        phase_shift_control = (
            self.phase_shift_control
            if phase_shift_control is None
            else phase_shift_control
        )
        phase_shift_target = (
            self.phase_shift_target
            if phase_shift_target is None
            else phase_shift_target
        )

        owner = self.qubit_pair
        positive = _point_voltages(owner, self.point) if point is None else point

        negative = {k: -v for k, v in positive.items()}
        zero = {k: 0.0 for k, _ in positive.items()}
        vs = owner.voltage_sequence
        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]

        qua.align(*gates)
        # with qua.strict_timing_():
        vs.ramp_to_voltages(
            negative, duration=wait, ramp_duration=ramp, ensure_align=False
        )
        vs.ramp_to_voltages(
            positive, duration=wait, ramp_duration=2 * ramp, ensure_align=False
        )
        vs.ramp_to_voltages(
            zero,
            duration=16,
            ramp_duration=ramp,
            ensure_align=False,
        )

        qua.frame_rotation_2pi(
            phase_shift_control, self.qubit_pair.qubit_control.xy.name
        )
        qua.frame_rotation_2pi(phase_shift_target, self.qubit_pair.qubit_target.xy.name)

    def balance(self) -> None:
        """No-op: each ``apply`` already plays both polarities (self-balancing).

        Provided so calibration scripts can unconditionally call
        ``qubit_pair.cz.balance()`` and work whether the wired macro is this
        balanced variant or the unbalanced :class:`CZMacro` that requires it.
        """


@quam_dataclass
class BalancedDCz2QMacro(BalancedCz2QMacro):
    """Dynamically decoupled CZ: CZ – X180(control, target) – CZ.

    The two CZ halves sandwich simultaneous X180 pulses on both qubits,
    refocusing low-frequency noise while accumulating twice the exchange phase.
    Phase shifts are applied only after the second CZ half.
    """

    def apply(
        self,
        wait_duration: int | None = None,
        ramp_duration: int | None = None,
        point: str | None = None,
        phase_shift_control: float | None = None,
        phase_shift_target: float | None = None,
        **kwargs,
    ):
        # First CZ half — no phase shifts yet
        super().apply(
            wait_duration=wait_duration,
            ramp_duration=ramp_duration,
            point=point,
            phase_shift_control=0.0,
            phase_shift_target=0.0,
            **kwargs,
        )

        # Refocusing X180 on both qubits simultaneously
        control = self.qubit_pair.qubit_control
        target = self.qubit_pair.qubit_target
        owner = self.qubit_pair
        vs = owner.voltage_sequence

        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]

        qua.align(control.xy.name, *gates)

        control.x180()

        qua.align(control.xy.name, target.xy.name)

        target.x180()

        qua.align(target.xy.name, *gates)

        # Second CZ half — apply accumulated phase shifts here
        super().apply(
            wait_duration=wait_duration,
            ramp_duration=ramp_duration,
            point=point,
            phase_shift_control=phase_shift_control,
            phase_shift_target=phase_shift_target,
            **kwargs,
        )


def _x180_pulse_name(drive_qubit, override: str | None = None) -> str:
    """Resolve the ESR pulse operation, defaulting to the qubit's calibrated x180.

    Mirrors the single-qubit macros: the pi pulse is ``{pulse_family}_x180``,
    resolved from the qubit's own ``x180`` macro so it tracks the active pulse
    family (see :class:`X180Macro`). Falls back to ``gaussian_x180`` if the macro
    is unavailable. An explicit *override* always wins.
    """
    if override is not None:
        return override
    x180_macro = getattr(drive_qubit, "macros", {}).get(SingleQubitMacroName.X_180.value)
    pulse_name = getattr(x180_macro, "pulse_name", None)
    if pulse_name is None:
        pulse_name = f"{DrivePulseName.GAUSSIAN.value}_x180"
    return pulse_name


@quam_dataclass
class BalancedCROTMacro(QubitPairMacro):
    """Step a qubit pair to a point, play one ESR pulse, then return to initialize.

    The ESR pulse is emitted on the driven qubit's XY channel. During the pulse
    the macro schedules an empty voltage-sequence segment on the pair so
    sticky-voltage tracking stays aligned with the microwave pulse duration.

    The pulse defaults to the driven qubit's calibrated ``x180`` operation (the
    same pi pulse used by the single-qubit macros); when ``duration`` and
    ``amplitude`` are not given, the x180 pulse's native length and amplitude
    are used.
    """

    pulse_name: str | None = None
    point: str | None = VoltagePointName.EXCHANGE.value
    ramp_duration: int | None = DEFAULTS.exchange.ramp_duration
    return_point: str = VoltagePointName.INITIALIZE.value
    esr_frequency: float | None = None

    @property
    def drive_qubit(self):
        """Return the qubit whose XY channel should emit the ESR pulse."""
        drive_qubit = self.qubit_pair.qubit_target
        return drive_qubit

    @property
    def inferred_duration(self) -> float | None:
        pass

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        *,
        ramp_duration: int | None = None,
        point: str | None = None,
        esr_frequency: float | None = None,
        amplitude: float | None = None,
        duration: int | None = None,
        pulse_name: str | None = None,
        drive_target: bool = True,
        **kwargs,
    ):
        """Execute the CROT sequence with runtime overrides.

        By default the ESR pulse is emitted on the target qubit's XY channel.
        Set ``drive_target=False`` to instead drive the control qubit (used by
        the symmetric branch of CROT spectroscopy, where the roles of target
        and control are swapped).
        """
        target_point = self.point if point is None else point

        if target_point is None:
            raise ValueError("CROTMacro requires a voltage_point.")

        drive_qubit = self.drive_qubit if drive_target else self.qubit_pair.qubit_control
        ramp_duration = self.ramp_duration if ramp_duration is None else ramp_duration
        pulse_name = _x180_pulse_name(
            drive_qubit, self.pulse_name if pulse_name is None else pulse_name
        )

        esr_frequency = self.esr_frequency if esr_frequency is None else esr_frequency

        if esr_frequency is not None:
            larmor_frequency = drive_qubit.larmor_frequency
            drive_qubit.xy.update_frequency(esr_frequency)

        owner = self.qubit_pair

        positive = _point_voltages(owner, target_point)
        negative = {k: -v for k, v in positive.items()}
        zero = {k: 0.0 for k, _ in positive.items()}
        vs = owner.voltage_sequence
        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]

        pulse_duration = drive_qubit.xy.operations[pulse_name].length if duration is None else duration
        qua.align(drive_qubit.xy.name, *gates)
        with qua.strict_timing_():
            qua.wait(int((3*ramp_duration + pulse_duration)//4), drive_qubit.xy.name)

            drive_qubit.xy.play(
                pulse_name,
                amplitude_scale=amplitude,
                duration=int(pulse_duration // 4),
            )

            vs.ramp_to_voltages(
                negative, duration=pulse_duration, ramp_duration=ramp_duration, ensure_align=False
            )
            vs.ramp_to_voltages(
                positive, duration=pulse_duration, ramp_duration=2 * ramp_duration, ensure_align=False
            )
            vs.ramp_to_voltages(
                zero,
                duration=16,
                ramp_duration=ramp_duration,
                ensure_align=False,
            )

        if esr_frequency is not None:
            drive_qubit.xy.update_frequency(larmor_frequency)

    def balance(self) -> None:
        """No-op: each ``apply`` already plays both polarities (self-balancing).

        Provided so calibration scripts can unconditionally call
        ``qubit_pair.crot.balance()`` and work whether the wired macro is this
        balanced variant or the unbalanced :class:`CROTMacro` that requires it.
        """
