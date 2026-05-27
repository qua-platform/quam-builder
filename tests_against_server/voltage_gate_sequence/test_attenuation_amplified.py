"""VoltageSequence with GateSet LF-FEM amplified outputs and non-zero attenuation."""

from validation_utils import simulate_program, validate_program, validate_compensation
from conftest import QuamGateSet
from qm import qua


def test_square_pulses_amplified_with_attenuation(qmm, machine_amplified: QuamGateSet):
    """Physical gate voltages match simulation when adjust_for_attenuation is on and ports are amplified."""
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

    qmm, samples = simulate_program(qmm, machine_amplified, prog, simulation_duration=20000)
    validate_program(samples, requested_wf_p, requested_wf_m)


def test_square_pulses_amplified_with_attenuation_qua(qmm, machine_amplified: QuamGateSet):
    """Same as test_square_pulses_amplified_with_attenuation but first plateau uses QUA fixed variables."""
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

    qmm, samples = simulate_program(qmm, machine_amplified, prog, simulation_duration=20000)
    validate_program(samples, requested_wf_p, requested_wf_m)


def test_qua_voltage_sequence_double_loop(qmm, machine: QuamGateSet):
    with qua.program() as program:
        amplitude_1 = qua.declare(qua.fixed)
        amplitude_2 = qua.declare(qua.fixed)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        machine.gate_set.add_point("init", {"ch1": 0.01, "ch2": -0.01}, duration=2000)
        machine.gate_set.add_point("init_return", {"ch1": 0, "ch2": 0}, duration=2000)

        with qua.for_each_(amplitude_1, [-0.01, 0.01]):
            with qua.for_each_(amplitude_2, [-0.01, 0.01]):
                seq.step_to_point("init")
                seq.step_to_point("init_return")
                seq.step_to_voltages(
                    voltages={"ch1": amplitude_1, "ch2": amplitude_2}, duration=2000
                )

                seq.step_to_point("init_return")
                seq.step_to_point("init")
                seq.apply_compensation_pulse(max_voltage=0.01)
                qua.wait(1000)

    qmm, samples = simulate_program(qmm, machine, program, int(1e5))
    validate_compensation(samples, allowed=100.0)


def test_qua_voltage_sequence_single_loop(qmm, machine: QuamGateSet):
    with qua.program() as program:
        amplitude_1 = qua.declare(qua.fixed, value=-0.02)
        amplitude_2 = qua.declare(qua.fixed)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        machine.gate_set.add_point("init", {"ch1": 0.02, "ch2": -0.02}, duration=2000)
        machine.gate_set.add_point("init_return", {"ch1": 0, "ch2": 0}, duration=2000)
        with qua.for_each_(amplitude_2, [-0.02, 0.02]):
            seq.step_to_point("init")
            seq.step_to_point("init_return")
            seq.step_to_voltages(voltages={"ch1": amplitude_1, "ch2": amplitude_2}, duration=2000)
            seq.step_to_point("init_return")
            seq.step_to_point("init")
            seq.apply_compensation_pulse(max_voltage=0.02)
            qua.wait(1000)

    qmm, samples = simulate_program(qmm, machine, program, int(5e4))
    validate_compensation(samples, allowed=100.0)


def test_python_voltage_sequence_zero_comp(qmm, machine: QuamGateSet):

    with qua.program() as program:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.01, "ch2": 0.01}, duration=100)
        seq.step_to_voltages(voltages={"ch1": -0.01, "ch2": -0.01}, duration=100)
        seq.apply_compensation_pulse(max_voltage=0.03)

    qmm, samples = simulate_program(qmm, machine, program, int(2e3))
    validate_compensation(samples)
