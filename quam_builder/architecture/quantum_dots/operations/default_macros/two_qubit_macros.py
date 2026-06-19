
"""Two-qubit default macros for quantum-dot qubit pairs."""

# Framework macro base classes introduce deep inheritance chains by design.
# pylint: disable=too-many-ancestors

from __future__ import annotations

import dataclasses

from qm import qua
from quam.components.macro import QubitPairMacro
from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    EmptyStateMacro,
    ExchangeStateMacro,
    InitializeStateMacro,
    MeasurePSBPairMacro,
    _owner_component,
    _resolve_default_point_duration_ns,
    _step_to_target,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    SingleQubitMacroName,
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.tools.qua_tools import DurationType, is_qua_type, validate_duration

__all__ = [
    "TWO_QUBIT_MACROS",
    "Initialize2QMacro",
    "Measure2QMacro",
    "Empty2QMacro",
    "Exchange2QMacro",
    "CROTMacro",
    "CNOTMacro",
    "CZMacro",
    "SwapMacro",
    "ISwapMacro",
    "DispatchInitialize2QMacro"
]


def _state_macro_field_names(macro_cls):
    """Return field names specific to a state macro, excluding QuamMacro base fields."""
    from quam.core.macro import QuamMacro

    try:
        base_names = {f.name for f in dataclasses.fields(QuamMacro)}
    except TypeError:
        base_names = set()
    try:
        all_names = {f.name for f in dataclasses.fields(macro_cls)}
    except TypeError:
        return set()
    return all_names - base_names


def _duration_ns_to_cycles(duration_ns: DurationType) -> DurationType:
    """Convert a nanosecond duration into OPX clock cycles."""
    validate_duration(duration_ns, "duration")
    if is_qua_type(duration_ns):
        return duration_ns >> 2
    return int(duration_ns) >> 2


def _runtime_frequency_hz(qubit, esr_frequency):
    """Convert an absolute ESR frequency to the channel update frequency."""
    drive = qubit.xy
    if drive is None:
        raise ValueError(f"Qubit '{qubit.id}' has no XY drive configured.")

    lo_frequency = None
    if hasattr(drive, "upconverter_frequency"):
        lo_frequency = drive.upconverter_frequency
    elif hasattr(drive, "LO_frequency"):
        lo_frequency = drive.LO_frequency

    if lo_frequency is None:
        return (
            esr_frequency
            if is_qua_type(esr_frequency)
            else int(round(float(esr_frequency)))
        )

    target_frequency = esr_frequency - lo_frequency
    if is_qua_type(target_frequency):
        return target_frequency

    target_frequency = int(round(float(target_frequency)))
    limit = getattr(drive, "IF_LIMIT", None)
    if isinstance(limit, (int, float)) and abs(target_frequency) > limit:
        raise ValueError(
            f"Requested ESR frequency maps to intermediate frequency "
            f"{target_frequency / 1e6:.2f} MHz, exceeding ±{limit / 1e6:.0f} MHz."
        )

    return target_frequency


def _point_voltages(owner, point: str | dict) -> dict[str, float]:
    """Resolve a voltage point name (or explicit voltage dict) to channel voltages."""
    if isinstance(point, dict):
        return point
    full_name = owner._create_point_name(point)
    tuning_point = owner.voltage_sequence.gate_set.macros.get(full_name)
    return dict(tuning_point.voltages)


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


class _CZBalanceCache:
    """In-memory record of CZ applications awaiting DC balancing.

    Each :meth:`CZMacro.apply` appends the resolved arguments of the
    positive-polarity exchange leg it played. :meth:`CZMacro.balance` later
    replays the mirror (negative-polarity) leg for every recorded call via
    :meth:`CZMacro.apply_inverse`, then clears the cache, so the net
    integrated voltage on every channel returns to zero.

    This is transient program state, not part of the QUAM configuration, so
    the field holding it is excluded from serialisation.
    """

    def __init__(self) -> None:
        self._calls: list[dict] = []

    def record(self, **call_kwargs) -> None:
        """Store the resolved arguments of a single ``apply`` call."""
        self._calls.append(dict(call_kwargs))

    def __iter__(self):
        return iter(self._calls)

    def __len__(self) -> int:
        return len(self._calls)

    def clear(self) -> None:
        """Drop all recorded calls."""
        self._calls.clear()


class Initialize2QMacro(QubitPairMacro):
    """Initialize qubit pair by delegating to QuantumDotPair's initialize macro."""

    _CANONICAL_MACRO_NAME = "initialize"

    def _resolve_canonical_macro(self):
        owner = _owner_component(self)
        qd_pair = getattr(owner, "quantum_dot_pair", None)
        if qd_pair is None:
            raise ValueError(
                f"LDQubitPair '{owner.id}' has no quantum_dot_pair for initialization."
            )
        return qd_pair.macros[self._CANONICAL_MACRO_NAME]

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

    def apply(self, qubit_role: str | None = None, **kwargs):
        owner = _owner_component(self)
        if kwargs.get("qubit_name") is None:
            role = "control" if qubit_role is None else qubit_role
            if role not in {"target", "control"}:
                raise ValueError(
                    f"Invalid qubit_role '{role}'. Expected 'target' or 'control'."
                )
            if role == "control":
                kwargs["qubit_name"] = owner.qubit_control.name
            else:
                kwargs["qubit_name"] = owner.qubit_target.name
        if kwargs.get("target_state") is None:
            pair_target_state = getattr(owner, "heralded_initialize_target_state", None)
            if pair_target_state is not None:
                kwargs["target_state"] = pair_target_state
        return self._resolve_canonical_macro().apply(xy_channel = owner.xy, **kwargs)

    def __getattr__(self, name):
        if name in _state_macro_field_names(InitializeStateMacro):
            return getattr(self._resolve_canonical_macro(), name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name, value):
        if name in _state_macro_field_names(InitializeStateMacro):
            setattr(self._resolve_canonical_macro(), name, value)
            return
        super().__setattr__(name, value)

class DispatchInitialize2QMacro(QubitPairMacro):
    """Initialize qubit pair by delegating to QuantumDotPair's initialize macro."""

    _CANONICAL_MACRO_NAME = "initialize"

    def apply(self, **kwargs):
        owner = _owner_component(self)
        owner.qubit_target.initialize(**kwargs)
        owner.qubit_control.initialize(**kwargs)


class Measure2QMacro(QubitPairMacro):
    """PSB measure macro for LDQubitPair.

    Delegates to the underlying QuantumDotPair's measure macro,
    which performs the full PSB readout chain.
    """

    _CANONICAL_MACRO_NAME = "measure"

    def _resolve_canonical_macro(self):
        owner = _owner_component(self)
        qd_pair = getattr(owner, "quantum_dot_pair", None)
        if qd_pair is None:
            raise ValueError(
                f"LDQubitPair '{owner.id}' has no quantum_dot_pair for readout."
            )
        return qd_pair.macros[self._CANONICAL_MACRO_NAME]

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
        if name in _state_macro_field_names(MeasurePSBPairMacro):
            return getattr(self._resolve_canonical_macro(), name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name, value):
        if name in _state_macro_field_names(MeasurePSBPairMacro):
            setattr(self._resolve_canonical_macro(), name, value)
            return
        super().__setattr__(name, value)


class Empty2QMacro(QubitPairMacro):
    """Move qubit pair to empty by delegating to QuantumDotPair's empty macro."""

    _CANONICAL_MACRO_NAME = "empty"

    def _resolve_canonical_macro(self):
        owner = _owner_component(self)
        qd_pair = getattr(owner, "quantum_dot_pair", None)
        if qd_pair is None:
            raise ValueError(
                f"LDQubitPair '{owner.id}' has no quantum_dot_pair for empty."
            )
        return qd_pair.macros[self._CANONICAL_MACRO_NAME]

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
        if name in _state_macro_field_names(EmptyStateMacro):
            return getattr(self._resolve_canonical_macro(), name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name, value):
        if name in _state_macro_field_names(EmptyStateMacro):
            setattr(self._resolve_canonical_macro(), name, value)
            return
        super().__setattr__(name, value)


class Exchange2QMacro(ExchangeStateMacro, QubitPairMacro):
    """Exchange macro for LDQubitPair — ramp to exchange, wait, ramp back."""

    point: str = VoltagePointName.EXCHANGE.value


class _CROTBalanceCache:
    """In-memory record of CROT exchange legs awaiting DC balancing.

    Each :meth:`CROTMacro.apply` appends the resolved arguments of the
    single-polarity exchange leg it played (the leg during which the ESR pulse
    drives the qubit). :meth:`CROTMacro.balance` later replays the mirror
    (opposite-polarity) leg for every recorded call via
    :meth:`CROTMacro.apply_inverse`, then clears the cache, so the net
    integrated voltage on every channel returns to zero.

    This is transient program state, not part of the QUAM configuration, so the
    field holding it is excluded from serialisation.
    """

    def __init__(self) -> None:
        self._calls: list[dict] = []

    def record(self, **call_kwargs) -> None:
        """Store the resolved arguments of a single ``apply`` call."""
        self._calls.append(dict(call_kwargs))

    def __iter__(self):
        return iter(self._calls)

    def __len__(self) -> int:
        return len(self._calls)

    def clear(self) -> None:
        """Drop all recorded calls."""
        self._calls.clear()


@quam_dataclass
class CROTMacro(QubitPairMacro):
    """Unbalanced controlled-rotation (CROT) gate macro.

    Ramps the barrier gate from zero to the exchange voltage point (a single
    polarity), plays one ESR pulse on the driven qubit during the hold, then
    ramps back to zero. The single-polarity excursion accumulates a net DC
    voltage on every channel.

    Like :class:`CZMacro`, every ``apply`` records the exchange leg it played in
    a transient cache; calling :meth:`balance` replays the mirror
    (opposite-polarity) leg via :meth:`apply_inverse` for each recorded call and
    clears the cache. ``apply`` followed by ``apply_inverse`` (same arguments)
    reproduces the fully balanced pulse shape of :class:`BalancedCROTMacro`.

    By default the ESR pulse is emitted on the target qubit's XY channel; pass
    ``drive_target=False`` to drive the control qubit instead (used by the
    symmetric branch of CROT spectroscopy).

    The pulse defaults to the driven qubit's calibrated ``x180`` operation (the
    same pi pulse used by the single-qubit macros); when ``duration`` and
    ``amplitude`` are not given, the x180 pulse's native length and amplitude
    are used.
    """

    pulse_name: str | None = None
    point: str | None = VoltagePointName.EXCHANGE.value
    ramp_duration: int = DEFAULTS.exchange.ramp_duration
    """Ramp duration between zero and the exchange voltage point (ns)."""
    esr_frequency: float | None = None
    amplitude: float | None = None
    duration: int | None = None
    """ESR pulse / exchange-hold duration (ns). Defaults to the x180 pulse length."""

    _cache: "_CROTBalanceCache" = dataclasses.field(
        default_factory=_CROTBalanceCache,
        metadata={"skip_save": True, "exclude": True},
        repr=False,
        compare=False,
    )
    """Transient record of pending ``apply`` calls, replayed by :meth:`balance`.

    Excluded from serialisation — not part of the QUAM configuration.
    """

    def _drive_qubit(self, drive_target: bool):
        """Return the qubit whose XY channel emits the ESR pulse."""
        qubit = (
            self.qubit_pair.qubit_target
            if drive_target
            else self.qubit_pair.qubit_control
        )
        if getattr(qubit, "xy", None) is None:
            raise ValueError(
                f"Qubit '{qubit.id}' in pair '{self.qubit_pair.id}' has no XY drive configured."
            )
        return qubit

    def _pulse_duration_ns(self, drive_qubit, pulse_name: str, duration) -> int:
        """Resolve the ESR pulse duration in ns, defaulting to the pulse length."""
        if duration is not None:
            return duration
        if pulse_name not in drive_qubit.xy.operations:
            raise KeyError(
                f"Pulse operation '{pulse_name}' is not defined on qubit '{drive_qubit.id}'."
            )
        length = getattr(drive_qubit.xy.operations[pulse_name], "length", None)
        if length is None:
            raise ValueError(
                f"Pulse '{pulse_name}' on qubit '{drive_qubit.id}' does not expose a length."
            )
        return int(length)

    @property
    def inferred_duration(self) -> float | None:
        try:
            drive_qubit = self._drive_qubit(True)
            pulse_duration = self._pulse_duration_ns(
                drive_qubit, _x180_pulse_name(drive_qubit, self.pulse_name), self.duration
            )
        except (KeyError, ValueError):
            return None
        if is_qua_type(pulse_duration) or self.ramp_duration is None:
            return None
        return (pulse_duration + 2 * self.ramp_duration) * 1e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def _play_exchange_leg(self, *, voltages, pulse_duration, ramp) -> None:
        """Ramp 0 → ``voltages`` → hold ``pulse_duration`` → ramp back to 0.

        A pure voltage excursion with no drive — used for the balancing leg.
        """
        owner = self.qubit_pair
        zero = {k: 0.0 for k in voltages}
        vs = owner.voltage_sequence
        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]

        qua.align(*gates)
        vs.ramp_to_voltages(
            voltages, duration=pulse_duration, ramp_duration=ramp, ensure_align=False
        )
        vs.ramp_to_voltages(zero, duration=16, ramp_duration=ramp, ensure_align=False)

    def apply(
        self,
        *,
        point: str | dict | None = None,
        ramp_duration: DurationType | None = None,
        esr_frequency: float | None = None,
        amplitude: float | None = None,
        duration: DurationType | None = None,
        pulse_name: str | None = None,
        drive_target: bool = True,
        **kwargs,
    ):
        """Execute the (unbalanced) CROT pulse sequence.

        Plays the single-polarity exchange leg with the ESR pulse during the
        hold, then records the leg so it can be balanced later.

        Parameters
        ----------
        point : str or dict, optional
            Override for the exchange voltage point name (or explicit channel
            voltages). Defaults to the stored ``point``.
        ramp_duration : int or QUA variable, optional
            Override for the ramp duration (ns).
        esr_frequency : float or QUA variable, optional
            If given, the driven qubit's XY frequency is set to this value for
            the pulse and restored to its Larmor frequency afterwards.
        amplitude : float or QUA variable, optional
            Per-call amplitude scale for the ESR pulse.
        duration : int or QUA variable, optional
            ESR pulse / exchange-hold duration (ns). Defaults to the pulse length.
        pulse_name : str, optional
            Override for the ESR pulse name.
        drive_target : bool, optional
            Drive the target qubit (default) or the control qubit when ``False``.
        """
        target_point = self.point if point is None else point
        if target_point is None:
            raise ValueError("CROTMacro requires a voltage_point.")

        drive_qubit = self._drive_qubit(drive_target)
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        resolved_pulse_name = _x180_pulse_name(
            drive_qubit, self.pulse_name if pulse_name is None else pulse_name
        )
        pulse_amplitude = self.amplitude if amplitude is None else amplitude
        runtime_esr_frequency = (
            self.esr_frequency if esr_frequency is None else esr_frequency
        )
        pulse_duration = self._pulse_duration_ns(
            drive_qubit,
            resolved_pulse_name,
            self.duration if duration is None else duration,
        )

        positive = _point_voltages(self.qubit_pair, target_point)
        zero = {k: 0.0 for k in positive}
        vs = self.qubit_pair.voltage_sequence
        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]

        play_kwargs = {"duration": _duration_ns_to_cycles(pulse_duration)}
        if pulse_amplitude is not None:
            play_kwargs["amplitude_scale"] = pulse_amplitude

        if runtime_esr_frequency is not None:
            larmor_frequency = drive_qubit.larmor_frequency
            drive_qubit.xy.update_frequency(runtime_esr_frequency)

        qua.align(drive_qubit.xy.name, *gates)
        with qua.strict_timing_():
            qua.wait(int((3 * ramp + pulse_duration) // 4), drive_qubit.xy.name)
            drive_qubit.xy.play(resolved_pulse_name, **play_kwargs)
            vs.ramp_to_voltages(
                positive, duration=pulse_duration, ramp_duration=ramp, ensure_align=False
            )
            vs.ramp_to_voltages(
                zero, duration=16, ramp_duration=ramp, ensure_align=False
            )

        if runtime_esr_frequency is not None:
            drive_qubit.xy.update_frequency(larmor_frequency)

        # Record the mirror leg so balance() can cancel the net DC later.
        self._cache.record(
            point=target_point, ramp_duration=ramp, duration=pulse_duration
        )

    def apply_inverse(
        self,
        *,
        point: str | dict | None = None,
        ramp_duration: DurationType | None = None,
        duration: DurationType | None = None,
        drive_target: bool = True,
        **kwargs,
    ):
        """Play the balancing (opposite-polarity) mirror of :meth:`apply`.

        Ramps to the element-wise negation of the exchange point, holds for the
        same duration, then ramps back to zero. No ESR pulse and no frequency
        update — this is purely the DC-balancing leg. It is not recorded.
        """
        target_point = self.point if point is None else point
        if target_point is None:
            raise ValueError("CROTMacro requires a voltage_point.")
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        drive_qubit = self._drive_qubit(drive_target)
        pulse_duration = self._pulse_duration_ns(
            drive_qubit, _x180_pulse_name(drive_qubit, self.pulse_name), duration
        )

        positive = _point_voltages(self.qubit_pair, target_point)
        negative = {k: -v for k, v in positive.items()}
        self._play_exchange_leg(
            voltages=negative, pulse_duration=pulse_duration, ramp=ramp
        )

    def balance(self) -> None:
        """Replay :meth:`apply_inverse` for every cached ``apply`` call, in
        order, then clear the cache.

        After this the net integrated voltage from all balanced ``apply`` calls
        is zero on every channel.
        """
        for call in self._cache:
            self.apply_inverse(**call)
        self._cache.clear()

    def update(
        self,
        *,
        point: str | None = None,
        ramp_duration: int | None = None,
        esr_frequency: float | None = None,
        amplitude: float | None = None,
        duration: int | None = None,
    ) -> None:
        if point is not None:
            self.point = point
        if ramp_duration is not None:
            self.ramp_duration = ramp_duration
        if esr_frequency is not None:
            self.esr_frequency = esr_frequency
        if amplitude is not None:
            self.amplitude = amplitude
        if duration is not None:
            self.duration = duration


class _Unsupported2QGateMacro(QubitPairMacro):
    """Default placeholder for two-qubit gates requiring calibration-specific logic."""

    gate_name: str

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        """Raise explicit guidance to register a calibration-specific override."""
        raise NotImplementedError(
            f"Default macro for '{self.gate_name}' is not yet implemented for "
            f"component '{self.qubit_pair.id}'. Register a calibrated macro override."
        )


class CNOTMacro(_Unsupported2QGateMacro):
    """Default placeholder for CNOT (override required)."""

    gate_name: str = TwoQubitMacroName.CNOT.value


@quam_dataclass
class CZMacro(QubitPairMacro):
    """Geometric CZ gate macro — a single (unbalanced) exchange pulse followed
    by virtual Z phase corrections on both qubits.

    The gate ramps the barrier gate to the calibrated CZ voltage point, holds
    for a calibrated duration, then ramps back to zero. The exchange produces
    a CZ up to single-qubit Z rotations, which are cancelled by virtual Z
    (frame) rotations applied after the ramp-back. These corrections are
    calibrated by the CZ phase compensation node.

    Unlike :class:`BalancedCz2QMacro`, ``apply`` plays only the positive
    exchange leg, so each call accumulates a net DC voltage. To recover DC
    balance, every ``apply`` is recorded in a transient cache; calling
    :meth:`balance` replays the mirror (negative-polarity) leg via
    :meth:`apply_inverse` for each recorded call and clears the cache.
    ``apply`` followed by ``apply_inverse`` (same arguments) reproduces the
    fully balanced pulse shape.
    """

    point: str = VoltagePointName.CZ.value if hasattr(VoltagePointName, "CZ") else "CZ"
    wait_duration: int = DEFAULTS.exchange.cz_duration
    """Hold duration at the CZ voltage point (ns)."""
    ramp_duration: int = DEFAULTS.exchange.ramp_duration
    """Ramp duration between zero and the CZ voltage point (ns)."""
    phase_shift_control: float = 0.0
    """Frame rotation on control qubit after CZ (units of 2pi)."""
    phase_shift_target: float = 0.0
    """Frame rotation on target qubit after CZ (units of 2pi)."""

    exchange_decay_model: dict | None = None
    """Fitted T_2π(V) model from ``18a_swap_oscillations``.

    Serialisable dict with a ``"type"`` key that identifies the function::

        {
            "type": "polynomial",
            "coeffs": [c_n, ..., c_0],   # highest-degree-first
            "degree": int,
        }

    ``None`` if not yet calibrated.  Consumed by downstream nodes such as
    ``18b_geometric_cz_amplitude_phase_calibration`` to evaluate a
    per-amplitude CZ duration via :meth:`t_2pi` / :meth:`t_cz`.
    """

    _cache: "_CZBalanceCache" = dataclasses.field(
        default_factory=_CZBalanceCache,
        metadata={"skip_save": True, "exclude": True},
        repr=False,
        compare=False,
    )
    """Transient record of pending ``apply`` calls, replayed by :meth:`balance`.

    Excluded from serialisation — not part of the QUAM configuration.
    """

    @property
    def inferred_duration(self) -> float | None:
        if self.wait_duration is None:
            return None
        return (self.wait_duration + 2 * self.ramp_duration) * 1e-9

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
            Half-period in nanoseconds (round to 4 ns for the QUA clock).
        """
        return self.t_2pi(amplitude) / 2.0

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def _play_exchange_leg(self, *, voltages, wait, ramp) -> None:
        """Ramp every channel 0 → ``voltages`` → hold ``wait`` → ramp back to 0."""
        owner = self.qubit_pair
        zero = {k: 0.0 for k in voltages}
        vs = owner.voltage_sequence
        gates = [ch_name for ch_name in vs.gate_set.channels.keys()]

        qua.align(*gates)
        vs.ramp_to_voltages(
            voltages, duration=wait, ramp_duration=ramp, ensure_align=False
        )
        vs.ramp_to_voltages(
            zero, duration=16, ramp_duration=ramp, ensure_align=False
        )

    def apply(
        self,
        *,
        point: str | dict | None = None,
        wait_duration: DurationType | None = None,
        ramp_duration: DurationType | None = None,
        phase_shift_control=None,
        phase_shift_target=None,
        **kwargs,
    ):
        """Execute the (unbalanced) CZ gate pulse sequence.

        Plays the positive-polarity exchange leg, records the call so it can be
        balanced later, and applies the virtual Z frame rotations.

        Parameters
        ----------
        point : str or dict, optional
            Override for the CZ voltage point name (or explicit channel
            voltages). Defaults to the stored ``point``.
        wait_duration : int or QUA variable, optional
            Override for the hold duration (ns).
        ramp_duration : int or QUA variable, optional
            Override for the ramp duration (ns).
        phase_shift_control : float or QUA variable, optional
            Per-call override for control qubit frame rotation (units of 2pi).
            If None, uses the stored ``phase_shift_control`` attribute.
        phase_shift_target : float or QUA variable, optional
            Per-call override for target qubit frame rotation (units of 2pi).
            If None, uses the stored ``phase_shift_target`` attribute.
        """
        cz_point = self.point if point is None else point
        wait = self.wait_duration if wait_duration is None else wait_duration
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration
        ctrl_phase = (
            self.phase_shift_control
            if phase_shift_control is None
            else phase_shift_control
        )
        tgt_phase = (
            self.phase_shift_target
            if phase_shift_target is None
            else phase_shift_target
        )

        positive = _point_voltages(self.qubit_pair, cz_point)
        self._play_exchange_leg(voltages=positive, wait=wait, ramp=ramp)

        # Record the mirror leg so balance() can cancel the net DC later.
        self._cache.record(point=cz_point, wait_duration=wait, ramp_duration=ramp)

        qua.frame_rotation_2pi(ctrl_phase, self.qubit_pair.qubit_control.xy.name)
        qua.frame_rotation_2pi(tgt_phase, self.qubit_pair.qubit_target.xy.name)

    def apply_inverse(
        self,
        *,
        point: str | dict | None = None,
        wait_duration: DurationType | None = None,
        ramp_duration: DurationType | None = None,
        **kwargs,
    ):
        """Play the balancing (negative-polarity) mirror of :meth:`apply`.

        Ramps to the element-wise negation of the CZ point, holds for the same
        duration, then ramps back to zero. No frame rotations are applied — this
        is purely the DC-balancing leg. It is not recorded in the cache.
        """
        cz_point = self.point if point is None else point
        wait = self.wait_duration if wait_duration is None else wait_duration
        ramp = self.ramp_duration if ramp_duration is None else ramp_duration

        positive = _point_voltages(self.qubit_pair, cz_point)
        negative = {k: -v for k, v in positive.items()}
        self._play_exchange_leg(voltages=negative, wait=wait, ramp=ramp)

    def balance(self) -> None:
        """Replay :meth:`apply_inverse` for every cached ``apply`` call, in
        order, then clear the cache.

        After this the net integrated voltage from all balanced ``apply`` calls
        is zero on every channel.
        """
        for call in self._cache:
            self.apply_inverse(**call)
        self._cache.clear()

    def update(
        self,
        *,
        wait_duration: int | None = None,
        ramp_duration: int | None = None,
        point: str | None = None,
        phase_shift_control: float | None = None,
        phase_shift_target: float | None = None,
        exchange_decay_model: dict | None = None,
    ) -> None:
        if wait_duration is not None:
            self.wait_duration = wait_duration
        if ramp_duration is not None:
            self.ramp_duration = ramp_duration
        if point is not None:
            self.point = point
        if phase_shift_control is not None:
            self.phase_shift_control = phase_shift_control
        if phase_shift_target is not None:
            self.phase_shift_target = phase_shift_target
        if exchange_decay_model is not None:
            self.exchange_decay_model = exchange_decay_model


class SwapMacro(_Unsupported2QGateMacro):
    """Default placeholder for SWAP (override required)."""

    gate_name: str = TwoQubitMacroName.SWAP.value


class ISwapMacro(_Unsupported2QGateMacro):
    """Default placeholder for iSWAP (override required)."""

    gate_name: str = TwoQubitMacroName.ISWAP.value


TWO_QUBIT_MACROS = {
    VoltagePointName.INITIALIZE.value: Initialize2QMacro,
    VoltagePointName.MEASURE.value: Measure2QMacro,
    VoltagePointName.EMPTY.value: Empty2QMacro,
    TwoQubitMacroName.CNOT.value: CNOTMacro,
    TwoQubitMacroName.CZ.value: CZMacro,
    TwoQubitMacroName.CROT.value: CROTMacro,
    TwoQubitMacroName.SWAP.value: SwapMacro,
    TwoQubitMacroName.ISWAP.value: ISwapMacro,
    TwoQubitMacroName.EXCHANGE.value: Exchange2QMacro,
}
# Default two-qubit macro factories for ``LDQubitPair`` components.
