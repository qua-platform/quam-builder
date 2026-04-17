"""Two-qubit default macros for quantum-dot qubit pairs."""

# Framework macro base classes introduce deep inheritance chains by design.
# pylint: disable=too-many-ancestors

from __future__ import annotations

from qm import qua
from quam.components.macro import QubitPairMacro
from quam.core import quam_dataclass
from quam_builder.architecture.quantum_dots.operations.default_macros.state_macros import (
    EmptyStateMacro,
    ExchangeStateMacro,
    InitializeStateMacro,
    _owner_component,
    _pulse_length_samples_to_ns,
    _resolve_default_point_duration_ns,
    _step_to_target,
)
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
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
]


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
        return esr_frequency if is_qua_type(esr_frequency) else int(round(float(esr_frequency)))

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


class Initialize2QMacro(InitializeStateMacro, QubitPairMacro):
    """Initialize qubit pair by ramping to the `initialize` voltage point."""

    point: str = VoltagePointName.INITIALIZE.value


class Measure2QMacro(QubitPairMacro):
    """PSB measure macro for LDQubitPair.

    Delegates to the underlying QuantumDotPair's measure macro,
    which performs the full PSB readout chain (voltage step -> sensor
    dot readout -> threshold -> QUA boolean).
    """

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(self, **kwargs):
        """Delegate measurement to the underlying quantum_dot_pair."""
        owner = _owner_component(self)
        qd_pair = getattr(owner, "quantum_dot_pair", None)
        if qd_pair is None:
            raise ValueError(f"LDQubitPair '{owner.id}' has no quantum_dot_pair for readout.")
        return qd_pair.macros[TwoQubitMacroName.MEASURE].apply(**kwargs)


class Empty2QMacro(EmptyStateMacro, QubitPairMacro):
    """Move qubit pair to the `empty` voltage point."""

    point: str = VoltagePointName.EMPTY.value


class Exchange2QMacro(ExchangeStateMacro, QubitPairMacro):
    """Exchange macro for LDQubitPair — ramp to exchange, wait, ramp back."""

    point: str = VoltagePointName.EXCHANGE.value


@quam_dataclass
class CROTMacro(QubitPairMacro):
    """Step a qubit pair to a point, play one ESR pulse, then return to initialize.

    The ESR pulse is emitted on the target qubit's XY channel. During the pulse
    the macro schedules an empty voltage-sequence segment on the pair so
    sticky-voltage tracking stays aligned with the microwave pulse duration.
    """

    pulse_name: str = DrivePulseName.GAUSSIAN.value
    voltage_point: str | None = VoltagePointName.EXCHANGE.value
    hold_time: int | None = None
    esr_frequency: float | None = None
    amplitude: float | None = None
    duration: int | None = None
    return_point: str = VoltagePointName.INITIALIZE.value

    @property
    def drive_qubit(self):
        """Return the qubit whose XY channel should emit the ESR pulse."""
        drive_qubit = self.qubit_pair.qubit_target
        if getattr(drive_qubit, "xy", None) is None:
            raise ValueError(
                f"Target qubit '{drive_qubit.id}' in pair '{self.qubit_pair.id}' has no XY drive configured."
            )
        return drive_qubit

    def _resolve_pulse_name(self, pulse_name: str | None) -> str:
        drive_qubit = self.drive_qubit
        resolved_name = self.pulse_name if pulse_name is None else pulse_name
        if resolved_name not in drive_qubit.xy.operations:
            raise KeyError(
                f"Pulse operation '{resolved_name}' is not defined on qubit '{drive_qubit.id}'."
            )
        return resolved_name

    def _pulse_length_ns(self, pulse_name: str) -> int:
        pulse = self.drive_qubit.xy.operations[pulse_name]
        length_ns = _pulse_length_samples_to_ns(getattr(pulse, "length", None))
        if length_ns is None:
            raise ValueError(
                f"Pulse '{pulse_name}' on qubit '{self.drive_qubit.id}' does not expose an integer length."
            )
        return length_ns

    @property
    def inferred_duration(self) -> float | None:
        target_point = self.voltage_point
        if target_point is None:
            return None

        hold_time = self.hold_time
        if hold_time is None:
            hold_time = _resolve_default_point_duration_ns(self.qubit_pair, target_point)

        if hold_time is None:
            return None

        try:
            pulse_duration = (
                self.duration
                if self.duration is not None
                else self._pulse_length_ns(self._resolve_pulse_name(None))
            )
        except (KeyError, ValueError):
            return None

        return (hold_time + pulse_duration) * 1e-9

    def __call__(self, *args, **kwargs):
        return self.apply(*args, **kwargs)

    def apply(
        self,
        *,
        voltage_point: str | None = None,
        hold_time: DurationType | None = None,
        esr_frequency: float | None = None,
        amplitude: float | None = None,
        duration: DurationType | None = None,
        pulse_name: str | None = None,
        **kwargs,
    ):
        """Execute the CROT sequence with runtime overrides."""
        target_point = self.voltage_point if voltage_point is None else voltage_point
        if target_point is None:
            raise ValueError("CROTMacro requires a voltage_point.")

        drive_qubit = self.drive_qubit
        point_hold_time = self.hold_time if hold_time is None else hold_time
        pulse_amplitude = self.amplitude if amplitude is None else amplitude
        pulse_duration_ns = self.duration if duration is None else duration
        runtime_esr_frequency = self.esr_frequency if esr_frequency is None else esr_frequency
        resolved_pulse_name = self._resolve_pulse_name(pulse_name)

        play_kwargs = dict(kwargs)
        if pulse_amplitude is not None:
            play_kwargs["amplitude_scale"] = pulse_amplitude

        if pulse_duration_ns is None:
            pulse_duration_ns = self._pulse_length_ns(resolved_pulse_name)
        else:
            play_kwargs["duration"] = _duration_ns_to_cycles(pulse_duration_ns)

        original_frequency = drive_qubit.xy.intermediate_frequency
        if not is_qua_type(original_frequency):
            original_frequency = int(round(float(original_frequency)))
        target_frequency = None
        if runtime_esr_frequency is not None:
            target_frequency = _runtime_frequency_hz(drive_qubit, runtime_esr_frequency)

        _step_to_target(self.qubit_pair, target_point, duration=point_hold_time)

        # qua.align()

        self.qubit_pair.align()

        if target_frequency is not None:
            drive_qubit.xy.update_frequency(target_frequency)

        # qua.align()

        self.qubit_pair.voltage_sequence.step_to_voltages({}, duration=pulse_duration_ns)
        drive_qubit.xy.play(
            pulse_name=resolved_pulse_name,
            **play_kwargs,
        )

        if target_frequency is not None:
            drive_qubit.xy.update_frequency(original_frequency)

        self.qubit_pair.align()
        # qua.align()

        self.qubit_pair.step_to_point(self.return_point, duration=16)


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


class CZMacro(_Unsupported2QGateMacro):
    """Default placeholder for CZ (override required)."""

    gate_name: str = TwoQubitMacroName.CZ.value


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
