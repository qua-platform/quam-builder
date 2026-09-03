"""VoltageSequence with GateSet LF-FEM amplified outputs and non-zero attenuation."""

import numpy as np
from conftest import QuamGateSet
from qm import qua

from validation_utils import simulate_program, validate_compensation, validate_program


def test_square_pulses_amplified_with_attenuation(qmm_saas, machine_amplified: QuamGateSet):
    """Simulated OPX analog samples match requested physical voltages after
    attenuation scaling, for three Python step_to_point plateaus on amplified
    LF-FEM ports. ramp_to_zero() is called but this assertion only covers the
    plateaus before the first return to 0 V."""
    level_init = [0.3, -0.1]
    duration_init = 1000
    level_manip = [0.5, -0.3]
    duration_manip = 100
    level_readout = [0.2, -0.2]
    duration_readout = 2000
    sampling_rate = 2

    requested_wf_p, requested_wf_m = [
        (
            [level_init[i]] * duration_init * sampling_rate
            + [level_manip[i]] * duration_manip * sampling_rate
            + [level_readout[i]] * duration_readout * sampling_rate
        )
        for i in range(2)
    ]

    atten_p = -machine_amplified.gate_set.channels["ch1"].attenuation
    atten_m = -machine_amplified.gate_set.channels["ch2"].attenuation
    attenuation_factor_p = 10 ** (atten_p / 20)
    attenuation_factor_m = 10 ** (atten_m / 20)
    requested_wf_p = [x / attenuation_factor_p for x in requested_wf_p]
    requested_wf_m = [x / attenuation_factor_m for x in requested_wf_m]
    machine_amplified.gate_set.add_point(
        "initialization",
        voltages={"ch1": level_init[0], "ch2": level_init[1]},
        duration=duration_init,
    )
    machine_amplified.gate_set.add_point(
        "idle",
        voltages={"ch1": level_manip[0], "ch2": level_manip[1]},
        duration=duration_manip,
    )
    machine_amplified.gate_set.add_point(
        "readout",
        voltages={"ch1": level_readout[0], "ch2": level_readout[1]},
        duration=duration_readout,
    )

    with qua.program() as prog:
        seq = machine_amplified.gate_set.new_sequence()
        seq.step_to_point("initialization")
        seq.step_to_point("idle")
        seq.step_to_point("readout")
        seq.ramp_to_zero()

    _, samples = simulate_program(qmm_saas, machine_amplified, prog, simulation_duration=20000)
    validate_program(samples, requested_wf_p, requested_wf_m)


def test_square_pulses_amplified_with_attenuation_qua(qmm_saas, machine_amplified: QuamGateSet):
    """Same plateau sequence as test_square_pulses_amplified_with_attenuation, but
    the first plateau is applied with QUA fixed variables via step_to_voltages.
    Checks that the QUA attenuation path (bit-shift / multiply) still matches
    the requested physical voltages on amplified ports."""
    level_init = [0.3, -0.1]
    duration_init = 1000
    level_manip = [0.5, -0.3]
    duration_manip = 100
    level_readout = [0.2, -0.2]
    duration_readout = 2000
    sampling_rate = 2

    machine_amplified.gate_set.add_point(
        "initialization",
        voltages={"ch1": level_init[0], "ch2": level_init[1]},
        duration=duration_init,
    )
    machine_amplified.gate_set.add_point(
        "idle",
        voltages={"ch1": level_manip[0], "ch2": level_manip[1]},
        duration=duration_manip,
    )
    machine_amplified.gate_set.add_point(
        "readout",
        voltages={"ch1": level_readout[0], "ch2": level_readout[1]},
        duration=duration_readout,
    )

    requested_wf_p, requested_wf_m = [
        (
            [level_init[i]] * duration_init * sampling_rate
            + [level_manip[i]] * duration_manip * sampling_rate
            + [level_readout[i]] * duration_readout * sampling_rate
        )
        for i in range(2)
    ]
    atten_p = -machine_amplified.gate_set.channels["ch1"].attenuation
    atten_m = -machine_amplified.gate_set.channels["ch2"].attenuation
    attenuation_factor_p = 10 ** (atten_p / 20)
    attenuation_factor_m = 10 ** (atten_m / 20)
    requested_wf_p = [x / attenuation_factor_p for x in requested_wf_p]
    requested_wf_m = [x / attenuation_factor_m for x in requested_wf_m]

    with qua.program() as prog:
        a = qua.declare(qua.fixed, value=level_init[0])
        b = qua.declare(qua.fixed, value=level_init[1])
        seq = machine_amplified.gate_set.new_sequence()
        seq.step_to_voltages(voltages={"ch1": a, "ch2": b}, duration=duration_init)
        seq.step_to_point("idle")
        seq.step_to_point("readout")
        seq.ramp_to_zero()

    _, samples = simulate_program(qmm_saas, machine_amplified, prog, simulation_duration=20000)
    validate_program(samples, requested_wf_p, requested_wf_m)


def test_amplified_python_compensation_cancels_step_integral(
    qmm_saas, machine_amplified: QuamGateSet
):
    """Python-only step_to_voltages on amplified+attenuated channels, followed by
    apply_compensation_pulse, leaves a near-zero analog integral on both outputs."""
    with qua.program() as program:
        seq = machine_amplified.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.01, "ch2": -0.01}, duration=100)
        seq.step_to_voltages(voltages={"ch1": 0.02, "ch2": -0.02}, duration=100)
        seq.step_to_voltages(voltages={"ch1": 0.03, "ch2": -0.03}, duration=100)
        seq.apply_compensation_pulse(max_voltage=0.03)

    _, samples = simulate_program(qmm_saas, machine_amplified, program, int(2e3))
    validate_compensation(samples, show_plot=False)


def test_amplified_qua_compensation_cancels_step_integral(
    qmm_saas, machine_amplified: QuamGateSet
):
    """Same three-step sequence as the Python compensation test, but voltage
    targets are QUA fixed variables. Checks the QUA compensation-parameter
    path on amplified ports with attenuation scaling."""
    with qua.program() as program:
        amplitude_1 = qua.declare(qua.fixed, value=0.01)
        amplitude_2 = qua.declare(qua.fixed, value=0.02)
        amplitude_3 = qua.declare(qua.fixed, value=0.03)
        seq = machine_amplified.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": amplitude_1, "ch2": -amplitude_1}, duration=100)
        seq.step_to_voltages(voltages={"ch1": amplitude_2, "ch2": -amplitude_2}, duration=100)
        seq.step_to_voltages(voltages={"ch1": amplitude_3, "ch2": -amplitude_3}, duration=100)
        seq.apply_compensation_pulse(max_voltage=0.03)

    _, samples = simulate_program(qmm_saas, machine_amplified, program, int(2e3))
    validate_compensation(samples, allowed=10.0, show_plot=False)


def test_amplified_ramp_to_zero_returns_analog_to_zero(
    qmm_saas, machine_amplified: QuamGateSet
):
    """With adjust_for_attenuation, ramp_to_zero() without a duration uses an
    explicit ramp (sticky duration, 100 ns here) instead of QUA ramp_to_zero.
    After a 100 ns step, both analog outputs end at approximately 0 V."""
    with qua.program() as program:
        seq = machine_amplified.gate_set.new_sequence()
        seq.step_to_voltages(voltages={"ch1": 0.05, "ch2": -0.05}, duration=100)
        seq.ramp_to_zero()

    _, samples = simulate_program(qmm_saas, machine_amplified, program, int(2e3))
    for name, sample in samples.con1.analog.items():
        tail = np.max(np.abs(np.asarray(sample[-50:])))
        assert tail < 0.02, f"{name} did not return to ~0 V after ramp_to_zero (tail max={tail})"


def test_amplified_python_ramps_then_compensation(qmm_saas, machine_amplified: QuamGateSet):
    """Python ramp_to_voltages on amplified+attenuated channels, then
    apply_compensation_pulse, leaves a near-zero analog integral."""
    with qua.program() as program:
        seq = machine_amplified.gate_set.new_sequence(track_integrated_voltage=True)
        seq.ramp_to_voltages(
            voltages={"ch1": 0.01, "ch2": -0.01}, duration=100, ramp_duration=16
        )
        seq.ramp_to_voltages(
            voltages={"ch1": 0.02, "ch2": -0.02}, duration=100, ramp_duration=16
        )
        seq.ramp_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16, ramp_duration=16)
        seq.apply_compensation_pulse(max_voltage=0.03)

    _, samples = simulate_program(qmm_saas, machine_amplified, program, int(3e3))
    validate_compensation(samples, show_plot=False)


def test_amplified_python_zero_net_steps_need_no_compensation(
    qmm_saas, machine_amplified: QuamGateSet
):
    """Equal-duration opposite Python steps on amplified channels cancel in the
    integral; apply_compensation_pulse should not leave a residual analog integral."""
    with qua.program() as program:
        seq = machine_amplified.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.01, "ch2": 0.01}, duration=100)
        seq.step_to_voltages(voltages={"ch1": -0.01, "ch2": -0.01}, duration=100)
        seq.apply_compensation_pulse(max_voltage=0.03)

    _, samples = simulate_program(qmm_saas, machine_amplified, program, int(2e3))
    validate_compensation(samples, show_plot=False)
