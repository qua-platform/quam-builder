"""Tests for the default (unbalanced, cache-and-balance) two-qubit CROT macro.

Like :class:`CZMacro`, ``CROTMacro.apply`` plays a single-polarity exchange leg
(with the ESR pulse during the hold) and records it; ``balance`` later replays
the opposite-polarity mirror leg via ``apply_inverse`` to cancel the net DC.
"""

from unittest.mock import call, patch

import pytest

from qm import qua
from quam.components.ports import MWFEMAnalogOutputPort
from quam_builder.architecture.quantum_dots.components import XYDriveMW
from quam_builder.architecture.quantum_dots.defaults import DEFAULTS
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.default_macros.two_qubit_macros import (
    CROTMacro,
)
from quam_builder.architecture.quantum_dots.operations.names import VoltagePointName

RAMP = DEFAULTS.exchange.ramp_duration
EXCHANGE_VOLTAGES = {"virtual_dot_1": 0.09, "virtual_dot_2": 0.16}
ZERO_VOLTAGES = {"virtual_dot_1": 0.0, "virtual_dot_2": 0.0}


def _add_drive(qubit, drive_id, fem_id, larmor=5.1e9):
    qubit.larmor_frequency = larmor
    qubit.xy = XYDriveMW(
        id=drive_id,
        opx_output=MWFEMAnalogOutputPort(
            controller_id="con1",
            fem_id=fem_id,
            port_id=1,
            band=2,
            upconverter_frequency=int(5e9),
            full_scale_power_dbm=10,
        ),
    )


@pytest.fixture
def pair_with_crot(qd_machine):
    """LD qubit pair with target + control MW drives and a default-wired CROT macro."""
    _add_drive(qd_machine.qubits["Q2"], "q2_xy", 1, larmor=5.1e9)
    _add_drive(qd_machine.qubits["Q1"], "q1_xy", 2, larmor=5.0e9)

    pair = qd_machine.qubit_pairs["Q1_Q2"]
    pair.add_point(
        VoltagePointName.INITIALIZE,
        {"virtual_dot_1": 0.05, "virtual_dot_2": 0.06},
        duration=200,
    )
    pair.add_point(
        VoltagePointName.EXCHANGE,
        EXCHANGE_VOLTAGES,
        duration=180,
    )

    wire_machine_macros(qd_machine)
    return pair


def test_crot_apply_plays_pulse_and_records_positive_leg(pair_with_crot):
    """apply() drives the target, ramps the positive exchange leg, and caches it."""
    pair = pair_with_crot
    target_qubit = pair.qubit_target
    crot = pair.macros["crot"]

    with qua.program():
        with (
            patch.object(pair.voltage_sequence, "ramp_to_voltages") as mock_ramp,
            patch.object(target_qubit.xy, "update_frequency") as mock_update_frequency,
            patch.object(target_qubit.xy, "play") as mock_play,
        ):
            crot.apply(
                point=VoltagePointName.EXCHANGE.value,
                esr_frequency=5.12e9,
                amplitude=0.4,
                duration=400,
            )

    mock_play.assert_called_once_with("gaussian_x180", duration=100, amplitude_scale=0.4)
    assert mock_ramp.call_args_list == [
        call(EXCHANGE_VOLTAGES, duration=400, ramp_duration=RAMP, ensure_align=False),
        call(ZERO_VOLTAGES, duration=16, ramp_duration=RAMP, ensure_align=False),
    ]
    # Frequency is set for the pulse, then restored to the Larmor frequency.
    assert mock_update_frequency.call_args_list == [call(5.12e9), call(5.1e9)]
    # A single pending leg awaits balancing.
    assert len(crot._cache) == 1


def test_crot_balance_replays_negative_leg_and_clears_cache(pair_with_crot):
    """balance() mirrors every cached apply() with the opposite polarity."""
    pair = pair_with_crot
    target_qubit = pair.qubit_target
    crot = pair.macros["crot"]

    negative = {k: -v for k, v in EXCHANGE_VOLTAGES.items()}

    with qua.program():
        with (
            patch.object(pair.voltage_sequence, "ramp_to_voltages") as mock_ramp,
            patch.object(target_qubit.xy, "play"),
        ):
            crot.apply(point=VoltagePointName.EXCHANGE.value, duration=400)
            assert len(crot._cache) == 1
            mock_ramp.reset_mock()

            crot.balance()

    assert mock_ramp.call_args_list == [
        call(negative, duration=400, ramp_duration=RAMP, ensure_align=False),
        call(ZERO_VOLTAGES, duration=16, ramp_duration=RAMP, ensure_align=False),
    ]
    assert len(crot._cache) == 0


def test_crot_drive_target_false_drives_control(pair_with_crot):
    """drive_target=False emits the ESR pulse on the control qubit's XY channel."""
    pair = pair_with_crot
    crot = pair.macros["crot"]

    with qua.program():
        with (
            patch.object(pair.voltage_sequence, "ramp_to_voltages"),
            patch.object(pair.qubit_target.xy, "play") as mock_target_play,
            patch.object(pair.qubit_control.xy, "play") as mock_control_play,
        ):
            crot.apply(
                point=VoltagePointName.EXCHANGE.value,
                duration=400,
                drive_target=False,
            )

    mock_target_play.assert_not_called()
    mock_control_play.assert_called_once_with("gaussian_x180", duration=100)


def test_crot_defaults_to_exchange_point_and_native_pulse_length(pair_with_crot):
    """Without overrides, apply() uses the exchange point and native pulse length."""
    pair = pair_with_crot
    target_qubit = pair.qubit_target
    crot = pair.macros["crot"]

    native_pulse_ns = target_qubit.xy.operations["gaussian_x180"].length

    with qua.program():
        with (
            patch.object(pair.voltage_sequence, "ramp_to_voltages") as mock_ramp,
            patch.object(target_qubit.xy, "play") as mock_play,
        ):
            crot.apply()

    mock_play.assert_called_once_with("gaussian_x180", duration=native_pulse_ns // 4)
    assert mock_ramp.call_args_list[0] == call(
        EXCHANGE_VOLTAGES, duration=native_pulse_ns, ramp_duration=RAMP, ensure_align=False
    )


def test_crot_inferred_duration(pair_with_crot):
    """Inferred duration = pulse duration + two ramps."""
    crot = CROTMacro(point=VoltagePointName.EXCHANGE.value, duration=400)
    pair_with_crot.set_macro("crot_duration", crot)
    assert crot.inferred_duration == pytest.approx((400 + 2 * RAMP) * 1e-9)


def test_crot_builds_a_valid_qua_program(pair_with_crot):
    """CROT should compile inside a QUA program with real pair and channel objects."""
    with qua.program() as prog:
        pair_with_crot.macros["crot"].apply(
            point=VoltagePointName.EXCHANGE.value,
            esr_frequency=5.12e9,
            amplitude=0.4,
            duration=400,
        )
        pair_with_crot.macros["crot"].balance()

    assert prog is not None


def test_crot_requires_drive_qubit_xy(qd_machine):
    """CROT should fail when the driven qubit has no XY drive configured."""
    pair = qd_machine.qubit_pairs["Q1_Q2"]
    pair.add_point(
        VoltagePointName.INITIALIZE,
        {"virtual_dot_1": 0.05, "virtual_dot_2": 0.06},
        duration=200,
    )
    pair.add_point(VoltagePointName.EXCHANGE, EXCHANGE_VOLTAGES, duration=180)

    wire_machine_macros(qd_machine)
    with pytest.raises(ValueError, match="has no XY drive configured"):
        pair.macros["crot"].apply(point=VoltagePointName.EXCHANGE.value, duration=400)