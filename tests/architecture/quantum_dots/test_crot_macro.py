"""Tests for the opt-in two-qubit CROT macro."""

from unittest.mock import call, patch

import pytest

from qm import qua
from quam.components.ports import MWFEMAnalogOutputPort
from quam_builder.architecture.quantum_dots.components import XYDriveMW
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.default_macros.two_qubit_macros import (
    CROTMacro,
)
from quam_builder.architecture.quantum_dots.operations.names import VoltagePointName


@pytest.fixture
def pair_with_crot(qd_machine):
    """LD qubit pair with a target-qubit MW drive and default-wired CROT macro."""
    target_qubit = qd_machine.qubits["Q2"]
    target_qubit.larmor_frequency = 5.1e9
    target_qubit.xy = XYDriveMW(
        id="q2_xy",
        opx_output=MWFEMAnalogOutputPort(
            controller_id="con1",
            fem_id=1,
            port_id=1,
            band=2,
            upconverter_frequency=int(5e9),
            full_scale_power_dbm=10,
        ),
    )

    pair = qd_machine.qubit_pairs["Q1_Q2"]
    pair.add_point(
        VoltagePointName.INITIALIZE,
        {"virtual_dot_1": 0.05, "virtual_dot_2": 0.06},
        duration=200,
    )
    pair.add_point(
        "operate",
        {"virtual_dot_1": 0.11, "virtual_dot_2": 0.14},
        duration=240,
    )
    pair.add_point(
        VoltagePointName.EXCHANGE,
        {"virtual_dot_1": 0.09, "virtual_dot_2": 0.16},
        duration=180,
    )

    wire_machine_macros(qd_machine)
    return pair


def test_crot_sequences_pair_point_tracking_esr_and_return(pair_with_crot):
    """CROT should step the pair, track the ESR pulse, restore frequency, and return."""
    pair = pair_with_crot
    target_qubit = pair.qubit_target
    crot = pair.macros["crot"]

    with (
        patch.object(pair, "step_to_point") as mock_step_to_point,
        patch.object(pair, "align") as mock_align,
        patch.object(pair.voltage_sequence, "step_to_voltages") as mock_track_pulse,
        patch.object(target_qubit.xy, "update_frequency") as mock_update_frequency,
        patch.object(target_qubit.xy, "play") as mock_play,
    ):
        crot.apply(
            voltage_point="operate",
            hold_time=80,
            esr_frequency=5.12e9,
            amplitude=0.4,
            duration=400,
        )

    assert mock_step_to_point.call_args_list == [
        call("operate", duration=80),
        call(VoltagePointName.INITIALIZE.value, duration=0),
    ]
    mock_align.assert_called_once_with()
    mock_track_pulse.assert_called_once_with({}, duration=400)
    assert mock_update_frequency.call_args_list == [call(120_000_000), call(100_000_000)]
    mock_play.assert_called_once_with(
        pulse_name="gaussian",
        amplitude_scale=0.4,
        duration=100,
    )


def test_crot_defaults_to_exchange_voltage_point(pair_with_crot):
    """Without an override, CROT should use the exchange voltage point."""
    pair = pair_with_crot
    target_qubit = pair.qubit_target
    crot = pair.macros["crot"]

    with (
        patch.object(pair, "step_to_point") as mock_step_to_point,
        patch.object(pair, "align") as mock_align,
        patch.object(pair.voltage_sequence, "step_to_voltages") as mock_track_pulse,
        patch.object(target_qubit.xy, "play") as mock_play,
    ):
        crot.apply(
            hold_time=40,
            amplitude=0.25,
        )

    assert mock_step_to_point.call_args_list == [
        call(VoltagePointName.EXCHANGE.value, duration=40),
        call(VoltagePointName.INITIALIZE.value, duration=0),
    ]
    mock_align.assert_called_once_with()
    mock_track_pulse.assert_called_once_with({}, duration=4000)
    mock_play.assert_called_once_with(
        pulse_name="gaussian",
        amplitude_scale=0.25,
    )


def test_crot_uses_native_pulse_length_when_duration_omitted(pair_with_crot):
    """Without an override, CROT should use the drive pulse's native length."""
    pair = pair_with_crot
    target_qubit = pair.qubit_target
    crot = pair.macros["crot"]

    with (
        patch.object(pair, "step_to_point") as mock_step_to_point,
        patch.object(pair, "align") as mock_align,
        patch.object(pair.voltage_sequence, "step_to_voltages") as mock_track_pulse,
        patch.object(target_qubit.xy, "update_frequency") as mock_update_frequency,
        patch.object(target_qubit.xy, "play") as mock_play,
    ):
        crot.apply(
            voltage_point="operate",
            hold_time=40,
            amplitude=0.25,
        )

    assert mock_step_to_point.call_args_list == [
        call("operate", duration=40),
        call(VoltagePointName.INITIALIZE.value, duration=0),
    ]
    mock_align.assert_called_once_with()
    mock_track_pulse.assert_called_once_with({}, duration=4000)
    mock_update_frequency.assert_not_called()
    mock_play.assert_called_once_with(
        pulse_name="gaussian",
        amplitude_scale=0.25,
    )


def test_crot_inferred_duration_uses_pair_point_hold_and_esr_duration(pair_with_crot):
    """Inferred duration should include the pair point hold and ESR pulse length."""
    crot = CROTMacro(
        voltage_point="operate",
        duration=400,
    )
    pair_with_crot.set_macro("crot_duration", crot)

    assert crot.inferred_duration == pytest.approx((240 + 400) * 1e-9)


def test_crot_inferred_duration_converts_native_pulse_length_samples(pair_with_crot):
    """Without an override, inferred duration should convert pulse samples to ns."""
    crot = CROTMacro(
        voltage_point="operate",
    )
    pair_with_crot.set_macro("crot_native_duration", crot)

    assert crot.inferred_duration == pytest.approx((240 + 4000) * 1e-9)


def test_crot_builds_a_valid_qua_program(pair_with_crot):
    """CROT should compile inside a QUA program with real pair and channel objects."""
    with qua.program() as prog:
        pair_with_crot.macros["crot"].apply(
            voltage_point="operate",
            hold_time=80,
            esr_frequency=5.12e9,
            amplitude=0.4,
            duration=400,
        )

    assert prog is not None


def test_crot_rejects_esr_frequency_beyond_mw_if_limit(pair_with_crot):
    """Absolute ESR frequency should be validated against the MW IF limit."""
    crot = pair_with_crot.macros["crot"]

    with pytest.raises(ValueError, match="exceeding"):
        crot.apply(
            voltage_point="operate",
            esr_frequency=5.7e9,
        )


def test_crot_requires_target_qubit_drive(qd_machine):
    """CROT should fail when only the control qubit has an XY drive."""
    control_qubit = qd_machine.qubits["Q1"]
    control_qubit.larmor_frequency = 5.1e9
    control_qubit.xy = XYDriveMW(
        id="q1_xy",
        opx_output=MWFEMAnalogOutputPort(
            controller_id="con1",
            fem_id=1,
            port_id=1,
            band=2,
            upconverter_frequency=int(5e9),
            full_scale_power_dbm=10,
        ),
    )

    pair = qd_machine.qubit_pairs["Q1_Q2"]
    pair.add_point(
        VoltagePointName.INITIALIZE,
        {"virtual_dot_1": 0.05, "virtual_dot_2": 0.06},
        duration=200,
    )
    pair.add_point(
        "operate",
        {"virtual_dot_1": 0.11, "virtual_dot_2": 0.14},
        duration=240,
    )

    wire_machine_macros(qd_machine)
    with pytest.raises(ValueError, match="Target qubit"):
        pair.macros["crot"].apply(voltage_point="operate")
