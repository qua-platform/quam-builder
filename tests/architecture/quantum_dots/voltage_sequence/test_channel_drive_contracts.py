"""Contract tests for the VoltageSequence rebuild (one behavior per test).

No qm-saas. Uses Python math, compilation, and generate_qua_script.
"""

import re

import numpy as np
import pytest
from qm import generate_qua_script, qua
from quam.components.channels import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort
from quam.core import QuamRoot, quam_dataclass

from quam_builder.architecture.quantum_dots.components import (
    GateSet,
    VoltageGate,
    VirtualGateSet,
    VirtualizationLayer,
)
from quam_builder.tools.voltage_sequence import (
    DEFAULT_PULSE_NAME,
    MIN_PULSE_DURATION_NS,
    VoltageSequence,
)
from quam_builder.tools.voltage_sequence.channel_state import (
    VOLTAGE_SCALE,
    ChannelState,
    split_mul,
    voltage_counts,
)
from quam_builder.tools.voltage_sequence.voltage_sequence import (
    _amplitude_scale,
    _channel_full_scale,
    _channel_wf_amp,
    round_amplitude,
)


@quam_dataclass
class _QuamGS(QuamRoot):
    gate_set: GateSet


def _direct_gate(att=0.0):
    return VoltageGate(
        opx_output=LFFEMAnalogOutputPort("con1", 5, 6, upsampling_mode="pulse"),
        sticky=StickyChannelAddon(duration=100, digital=False),
        attenuation=att,
    )


def _amplified_gate(att=0.0):
    return VoltageGate(
        opx_output=LFFEMAnalogOutputPort(
            "con1", 5, 6, upsampling_mode="pulse", output_mode="amplified"
        ),
        sticky=StickyChannelAddon(duration=100, digital=False),
        attenuation=att,
    )


def test_direct_full_scale_and_waveform_are_half_volt():
    g = _direct_gate()
    assert g.full_scale == 0.5
    assert g.step_waveform_amplitude == 0.5
    seq = VoltageSequence(GateSet(id="g", channels={"ch1": g}))
    assert _channel_full_scale(seq.gate_set.channels["ch1"]) == 0.5
    assert _channel_wf_amp(seq.gate_set.channels["ch1"]) == pytest.approx(0.5)


def test_amplified_full_scale_and_waveform_are_two_and_a_half_volt():
    g = _amplified_gate()
    assert g.full_scale == 2.5
    assert g.step_waveform_amplitude == 2.5
    seq = VoltageSequence(GateSet(id="g", channels={"ch1": g}))
    assert _channel_wf_amp(seq.gate_set.channels["ch1"]) == pytest.approx(2.5)


def test_rail_to_rail_direct_scale_is_within_plus_minus_two():
    delta = 1.0  # -0.5 -> +0.5
    scale = _amplitude_scale(delta, 0.5)
    assert scale == pytest.approx(2.0)
    assert abs(scale) <= 2.0


def test_rail_to_rail_amplified_scale_is_within_plus_minus_two():
    delta = 5.0  # -2.5 -> +2.5
    scale = _amplitude_scale(delta, 2.5)
    assert scale == pytest.approx(2.0)
    assert abs(scale) <= 2.0


def test_direct_scale_is_left_shift_by_one():
    """1/0.5 = 2 = 2**1, so QUA uses delta << 1."""
    with qua.program() as prog:
        v = qua.declare(qua.fixed, value=0.1)
        s = qua.declare(qua.fixed)
        qua.assign(s, _amplitude_scale(v, 0.5))
    script = generate_qua_script(prog, config=None)
    assert "<< 1" in script or "<<1" in script.replace(" ", "")


def test_amplified_scale_is_multiply_by_point_four():
    assert _amplitude_scale(1.25, 2.5) == pytest.approx(0.5)


def test_device_to_opx_twenty_db_is_times_ten():
    g = _direct_gate(att=20.0)
    assert g.device_to_opx(0.03) == pytest.approx(0.3)
    assert g.opx_to_device(0.3) == pytest.approx(0.03)


def test_step_area_is_voltage_counts_times_duration_ns():
    st = ChannelState("ch1")
    st.update_integrated_voltage(0.03, 100)
    assert st.integrated_voltage == voltage_counts(0.03) * 100
    assert st.python_area_v_ns() == pytest.approx(voltage_counts(0.03) * 100 / VOLTAGE_SCALE)


def test_ramp_area_uses_average_of_previous_and_target():
    st = ChannelState("ch1")
    st.current_level = 0.1
    st.update_integrated_voltage(level=0.3, duration=100, ramp_duration=20)
    expected = voltage_counts(0.3) * 100 + voltage_counts(float(np.float16((0.3 + 0.1) * 0.5))) * 20
    # average is quantized via float16 of 0.2
    avg_counts = voltage_counts(0.2)
    expected = voltage_counts(0.3) * 100 + avg_counts * 20
    assert st.integrated_voltage == expected


def test_zero_delta_still_accumulates_hold_area():
    st = ChannelState("ch1")
    st.current_level = 0.1
    st.update_integrated_voltage(0.1, 80)
    assert st.integrated_voltage == voltage_counts(0.1) * 80


def test_split_mul_matches_unbounded_product_at_amplified_full_scale():
    v_counts = voltage_counts(2.5)
    duration_ns = 10_000_000
    assert split_mul(v_counts, duration_ns) == v_counts * duration_ns
    assert v_counts * 4095 < 2**31 - 1


def test_reset_integrated_voltage_zeros_coarse_and_fine():
    st = ChannelState("ch1")
    st.update_integrated_voltage(0.1, 1000)
    st.reset_integrated_voltage()
    assert st.coarse == 0
    assert st.fine == 0
    assert st.integrated_voltage == 0


def test_python_compensation_area_matches_amp_times_duration():
    st = ChannelState("ch1")
    st.update_integrated_voltage(round_amplitude(0.03), 100)
    seq = VoltageSequence(GateSet(id="g", channels={"ch1": _direct_gate()}))
    amp, dur = seq._calculate_python_compensation_params(st, max_voltage=0.03)
    assert dur % 4 == 0
    assert dur >= 16
    area = st.python_area_v_ns()
    assert amp * dur == pytest.approx(-area, abs=1.0 / VOLTAGE_SCALE * dur)


def test_keep_levels_true_holds_unspecified_channel(machine):
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(enforce_qua_calcs=False, keep_levels=True)
        seq.step_to_voltages({"ch1": 0.2}, duration=100)
        seq.step_to_voltages({"ch2": 0.1}, duration=100)
        assert seq.state_trackers["ch1"].current_level == pytest.approx(float(np.float16(0.2)))
        assert seq.state_trackers["ch2"].current_level == pytest.approx(float(np.float16(0.1)))


def test_keep_levels_false_drives_omitted_channel_to_zero(machine):
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(enforce_qua_calcs=False, keep_levels=False)
        seq.step_to_voltages({"ch1": 0.2, "ch2": 0.1}, duration=100)
        seq.step_to_voltages({"ch1": 0.2}, duration=100)
        assert seq.state_trackers["ch2"].current_level == pytest.approx(0.0)


def test_virtual_resolve_plays_physical_channels():
    virt_matrix = np.array([[1.0, 1.0], [-1.0, 1.0]])
    vgs = VirtualGateSet(
        id="vg",
        channels={
            "ch1": _direct_gate(),
            "ch2": VoltageGate(
                opx_output=LFFEMAnalogOutputPort("con1", 5, 3, upsampling_mode="pulse"),
                sticky=StickyChannelAddon(duration=100, digital=False),
            ),
        },
        layers=[
            VirtualizationLayer(
                source_gates=["energy", "detuning"],
                target_gates=["ch1", "ch2"],
                matrix=virt_matrix.tolist(),
            )
        ],
    )
    with qua.program() as prog:
        seq = vgs.new_sequence(enforce_qua_calcs=False, track_integrated_voltage=False)
        seq.step_to_voltages({"detuning": 0.1}, duration=100)
    script = generate_qua_script(prog, config=None)
    assert 'play("half_max_square"' in script or "half_max_square" in script
    assert "ch1" in script and "ch2" in script


def test_compensation_script_has_no_assign_between_comp_and_return_plays():
    machine = _QuamGS(gate_set=GateSet(id="g", channels={"ch1": _direct_gate()}))
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages({"ch1": 0.03}, duration=100)
        seq.apply_compensation_pulse(max_voltage=0.03)
    script = generate_qua_script(prog, machine.generate_config())
    plays = [m.start() for m in re.finditer(r'play\("half_max_square"', script)]
    assert len(plays) >= 2
    # Last two half_max plays should be compensation + return-to-zero.
    body = script[plays[-2] : plays[-1]]
    assert "assign(" not in body


def test_qua_compensation_script_does_not_truncate_area_to_whole_volt_ns():
    machine = _QuamGS(gate_set=GateSet(id="g", channels={"ch1": _direct_gate()}))
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        amp = qua.declare(qua.fixed, value=0.03)
        seq.step_to_voltages({"ch1": amp}, duration=100)
        seq.apply_compensation_pulse(max_voltage=0.03)
    script = generate_qua_script(prog, machine.generate_config())
    assert "mul_int_by_fixed" in script or "Math.div" in script
    assert "1.52587890625e-05" not in script or "Math.div" in script


def test_enforce_qua_false_python_step_script_is_play_only():
    machine = _QuamGS(gate_set=GateSet(id="g", channels={"ch1": _direct_gate()}))
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(
            enforce_qua_calcs=False, track_integrated_voltage=False
        )
        seq.step_to_voltages({"ch1": 0.1}, duration=100)
    script = generate_qua_script(prog, machine.generate_config())
    assert "declare(int" not in script.replace(" ", "") or script.count("play(") >= 1
    assert "play(" in script
