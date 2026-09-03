"""VoltageSequence tests that do not compare QUA ASTs.

Covers error paths, integrated-voltage bookkeeping, compensation parameter
invariants, and channel voltage limits. These tests do not require qua-qsim.
"""

import numpy as np
import pytest
from qm import qua
from quam.components import pulses
from quam.components.channels import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort
from quam.core import QuamRoot, quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.components import GateSet, VoltageGate
from quam_builder.tools.qua_tools import is_qua_type
from quam_builder.tools.voltage_sequence import (
    DEFAULT_PULSE_NAME,
    MIN_PULSE_DURATION_NS,
    VoltageSequence,
)
from quam_builder.tools.voltage_sequence.exceptions import VoltagePointError
from quam_builder.tools.voltage_sequence.sequence_state_tracker import (
    INTEGRATED_VOLTAGE_SCALING_FACTOR,
)
from quam_builder.tools.voltage_sequence.voltage_sequence import (
    CLOCK_CYCLE_NS,
    COMPENSATION_SCALING_FACTOR,
    DEFAULT_QUA_COMPENSATION_DURATION_NS,
    round_amplitude,
)


@quam_dataclass
class _NotATuningPoint(QuamMacro):
    def apply(self, *args, **kwargs):
        pass


def _add_default_pulses(machine):
    for channel in machine.gate_set.channels.values():
        channel.operations[DEFAULT_PULSE_NAME] = pulses.SquarePulse(
            amplitude=0.25, length=MIN_PULSE_DURATION_NS
        )


def test_step_to_point_raises_when_macro_name_is_unknown(machine):
    """step_to_point raises VoltagePointError if the name is not in GateSet.macros."""
    seq = VoltageSequence(machine.gate_set)
    with pytest.raises(VoltagePointError, match="not a valid VoltageTuningPoint"):
        seq.step_to_point("does_not_exist")


def test_ramp_to_point_raises_when_macro_name_is_unknown(machine):
    """ramp_to_point raises VoltagePointError if the name is not in GateSet.macros."""
    seq = VoltageSequence(machine.gate_set)
    with pytest.raises(VoltagePointError, match="not a valid VoltageTuningPoint"):
        seq.ramp_to_point("does_not_exist", ramp_duration=40)


def test_step_to_point_raises_when_macro_is_not_a_voltage_tuning_point(machine):
    """step_to_point raises VoltagePointError when the named macro exists but is
    not a VoltageTuningPoint."""
    if getattr(machine.gate_set, "macros", None) is None:
        machine.gate_set.macros = {}
    machine.gate_set.macros["other"] = _NotATuningPoint()
    seq = VoltageSequence(machine.gate_set)
    with pytest.raises(VoltagePointError, match="not a valid VoltageTuningPoint"):
        seq.step_to_point("other")


def test_apply_compensation_pulse_raises_when_integrated_voltage_is_not_tracked(machine):
    """apply_compensation_pulse requires track_integrated_voltage=True.
    GateSet.new_sequence() defaults that flag to False."""
    with qua.program() as _prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=False)
        with pytest.raises(ValueError, match="not tracked"):
            seq.apply_compensation_pulse()


def test_apply_compensation_pulse_raises_when_max_voltage_is_not_positive(machine):
    """apply_compensation_pulse rejects max_voltage <= 0."""
    with qua.program() as _prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        with pytest.raises(ValueError, match="max_voltage must be positive"):
            seq.apply_compensation_pulse(max_voltage=0)
        with pytest.raises(ValueError, match="max_voltage must be positive"):
            seq.apply_compensation_pulse(max_voltage=-0.1)


def test_python_compensation_params_are_zero_when_integral_is_zero(machine):
    """_calculate_python_compensation_params returns (0.0, 0) when the
    channel has accumulated no integrated voltage."""
    seq = VoltageSequence(machine.gate_set, track_integrated_voltage=True)
    amp, dur = seq._calculate_python_compensation_params(
        seq.state_trackers["ch1"], max_voltage=0.4
    )
    assert amp == 0.0
    assert dur == 0


def test_python_compensation_params_cancel_accumulated_charge_within_max_voltage(
    machine,
):
    """For a Python-only integral, compensation duration is a 4 ns multiple of at
    least 48 ns, |amplitude| is within max_voltage, and amplitude * duration equals
    the negated accumulated charge (integral / 1024)."""
    seq = VoltageSequence(machine.gate_set, track_integrated_voltage=True)
    tracker = seq.state_trackers["ch1"]
    tracker.update_integrated_voltage(level=0.1, duration=1000)
    max_voltage = 0.4
    amp, dur = seq._calculate_python_compensation_params(tracker, max_voltage)

    charge = tracker.integrated_voltage * COMPENSATION_SCALING_FACTOR
    assert dur >= DEFAULT_QUA_COMPENSATION_DURATION_NS
    assert dur % CLOCK_CYCLE_NS == 0
    assert abs(amp) <= max_voltage
    assert np.isclose(-amp * dur, charge)


def test_apply_compensation_pulse_resets_python_integrated_voltage(machine):
    """After a Python-only step, apply_compensation_pulse resets every channel's
    integrated_voltage to 0 (required so a later loop iteration does not
    double-count)."""
    _add_default_pulses(machine)
    with qua.program() as _prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.1, "ch2": 0.1}, duration=1000)
        assert seq.state_trackers["ch1"].integrated_voltage != 0
        seq.apply_compensation_pulse(max_voltage=0.4)
        for tracker in seq.state_trackers.values():
            assert tracker.integrated_voltage == 0


def test_apply_compensation_pulse_return_to_zero_sets_current_level_to_zero(machine):
    """return_to_zero=True (default) steps every channel to 0 V after the
    compensation pulse, so current_level is 0 on all trackers."""
    _add_default_pulses(machine)
    with qua.program() as _prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.1, "ch2": -0.1}, duration=1000)
        seq.apply_compensation_pulse(max_voltage=0.4, return_to_zero=True)
        for tracker in seq.state_trackers.values():
            assert tracker.current_level == 0.0


def test_apply_compensation_pulse_without_return_to_zero_stays_at_compensation_amplitude(
    machine,
):
    """With go_to_zero=False and return_to_zero=False, current_level is left at
    the compensation amplitude (opposite sign to the accumulated voltage)
    rather than being stepped back to 0 V."""
    _add_default_pulses(machine)
    with qua.program() as _prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.1, "ch2": 0.1}, duration=1000)
        seq.apply_compensation_pulse(
            max_voltage=0.4, go_to_zero=False, return_to_zero=False
        )
        ch1_level = seq.state_trackers["ch1"].current_level
        assert ch1_level < 0
        assert abs(ch1_level) <= 0.4


def test_apply_compensation_pulse_clips_max_voltage_to_channel_limit(machine):
    """When max_voltage exceeds the channel OPX limit (0.5 V on a non-amplified
    SingleChannel), compensation amplitude is computed against that limit, not
    the caller-supplied value."""
    _add_default_pulses(machine)
    with qua.program() as _prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.1, "ch2": 0.1}, duration=5000)
        seq.apply_compensation_pulse(
            max_voltage=10.0, go_to_zero=False, return_to_zero=False
        )
        channel_limit = seq._channel_max_voltage["ch1"]
        assert channel_limit == pytest.approx(0.5)
        assert abs(seq.state_trackers["ch1"].current_level) <= channel_limit + 1e-9


def test_track_sticky_duration_adds_hold_time_at_current_level_to_the_integral(machine):
    """track_sticky_duration(N) adds current_level * N * 1024 to each channel's
    integral without playing a pulse. Used when another macro runs while sticky
    outputs hold a DC level."""
    _add_default_pulses(machine)
    with qua.program() as _prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.25, "ch2": 0.0}, duration=100)
        after_step = seq.state_trackers["ch1"].integrated_voltage
        seq.track_sticky_duration(200)
        extra = int(np.round(0.25 * 200 * INTEGRATED_VOLTAGE_SCALING_FACTOR))
        assert seq.state_trackers["ch1"].integrated_voltage == after_step + extra
        assert seq.state_trackers["ch2"].integrated_voltage == 0


def test_track_sticky_duration_zero_is_a_no_op(machine):
    """track_sticky_duration(0) does not change integrated_voltage."""
    seq = VoltageSequence(machine.gate_set, track_integrated_voltage=True)
    seq.state_trackers["ch1"].update_integrated_voltage(0.1, 100)
    before = seq.state_trackers["ch1"].integrated_voltage
    seq.track_sticky_duration(0)
    assert seq.state_trackers["ch1"].integrated_voltage == before


def test_track_sticky_duration_is_a_no_op_when_integrated_voltage_is_not_tracked(machine):
    """When track_integrated_voltage=False, track_sticky_duration returns immediately:
    invalid durations are not validated and the integral stays 0."""
    seq = machine.gate_set.new_sequence(track_integrated_voltage=False)
    seq.track_sticky_duration(7)
    assert seq.state_trackers["ch1"].integrated_voltage == 0


def test_track_sticky_duration_rejects_non_int_negative_and_non_multiple_of_4ns(machine):
    """With tracking enabled, duration_ns must be a non-negative int multiple of 4 ns."""
    seq = VoltageSequence(machine.gate_set, track_integrated_voltage=True)
    with pytest.raises(TypeError, match="integer number of nanoseconds"):
        seq.track_sticky_duration(16.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="non-negative"):
        seq.track_sticky_duration(-4)
    with pytest.raises(TypeError, match="multiple of 4"):
        seq.track_sticky_duration(18)


def test_reset_integrated_voltage_clears_all_channel_trackers(machine):
    """VoltageSequence.reset_integrated_voltage zeros every channel tracker."""
    seq = VoltageSequence(machine.gate_set, track_integrated_voltage=True)
    seq.state_trackers["ch1"].update_integrated_voltage(0.1, 100)
    seq.state_trackers["ch2"].update_integrated_voltage(-0.2, 80)
    seq.reset_integrated_voltage()
    assert seq.state_trackers["ch1"].integrated_voltage == 0
    assert seq.state_trackers["ch2"].integrated_voltage == 0


def test_round_amplitude_python_value_uses_float16_precision():
    """Python voltages are rounded to IEEE float16 so sticky accumulation does
    not drift from 16-bit OPX amplitude resolution."""
    assert round_amplitude(0.1) == float(np.float16(0.1))
    assert round_amplitude(0.25) == 0.25


def test_enforce_qua_calcs_on_new_sequence_declares_current_level_as_qua(machine):
    """new_sequence(enforce_qua_calcs=True) starts each channel current_level as a
    QUA fixed, so later Python steps assign into QUA rather than storing a float."""
    with qua.program() as _prog:
        seq = machine.gate_set.new_sequence(enforce_qua_calcs=True)
        assert is_qua_type(seq.state_trackers["ch1"].current_level)
        assert is_qua_type(seq.state_trackers["ch2"].current_level)


def test_direct_channel_max_voltage_is_half_volt(machine):
    """Without an amplified LF-FEM output_mode, each channel's compensation
    voltage cap is 0.5 V."""
    seq = VoltageSequence(machine.gate_set)
    assert seq._channel_max_voltage["ch1"] == pytest.approx(0.5)
    assert seq._channel_max_voltage["ch2"] == pytest.approx(0.5)


def test_amplified_channel_max_voltage_is_reduced_by_attenuation():
    """On an amplified LF-FEM port with adjust_for_attenuation, the compensation
    cap is 2.5 V divided by 10^(attenuation_dB/20)."""

    @quam_dataclass
    class _Machine(QuamRoot):
        gate_set: GateSet

    machine = _Machine(
        gate_set=GateSet(
            id="amplified_limits",
            channels={
                "ch1": VoltageGate(
                    opx_output=LFFEMAnalogOutputPort(
                        "con1", 5, 6, upsampling_mode="pulse", output_mode="amplified"
                    ),
                    sticky=StickyChannelAddon(duration=100, digital=False),
                    attenuation=10,
                )
            },
            adjust_for_attenuation=True,
        )
    )
    seq = VoltageSequence(machine.gate_set)
    expected = 2.5 / (10 ** (10 / 20))
    assert seq._channel_max_voltage["ch1"] == pytest.approx(expected)
