"""
Squares (Python) + Ramps (None) + Compensation (max_amplitude=0.45)
"""

from validation_utils import simulate_program, validate_program, validate_compensation
from conftest import QuamGateSet, QuamVirtualGateSet
from qm import qua

###################
# The QUA program #
###################

# %% 1 consecutive compensation pulses
print("1 single compensation pulse:")


def test_square_pulses_python(qmm, machine):
    """Tests stepping to a single predefined point."""
    level_init = [0.75, -0.1]
    duration_init = 1000
    level_manip = [0.5, -0.3]
    duration_manip = 100
    level_readout = [0.2, -0.2]
    duration_readout = 2000
    sampling_rate = 2
    max_compensation_amplitude = 0.2

    requested_wf_p, requested_wf_m = [
        (
            [level_init[i]] * duration_init * sampling_rate
            + [level_manip[i]] * duration_manip * sampling_rate
            + [level_readout[i]] * duration_readout * sampling_rate
        )
        for i in range(2)
    ]

    machine.gate_set.add_point(
        "initialization",
        voltages={"ch1": level_init[0], "ch2": level_init[1]},
        duration=duration_init,
    )
    machine.gate_set.add_point(
        "idle",
        voltages={"ch1": level_manip[0], "ch2": level_manip[1]},
        duration=duration_manip,
    )
    machine.gate_set.add_point(
        "readout",
        voltages={"ch1": level_readout[0], "ch2": level_readout[1]},
        duration=duration_readout,
    )

    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.step_to_point("initialization")
        seq.step_to_point("idle")
        seq.step_to_point("readout")
        seq.ramp_to_zero()

    qmm, samples = simulate_program(qmm, machine, prog, simulation_duration=20000)
    validate_program(samples, requested_wf_p, requested_wf_m)


def test_square_pulses_qua(qmm, machine):
    level_init = [0.8, -0.1]
    duration_init = 1000
    level_manip = [0.5, -0.3]
    duration_manip = 100
    level_readout = [0.2, -0.2]
    duration_readout = 2000
    max_compensation_amplitude = 0.2
    sampling_rate = 2

    # Add the relevant voltage points describing the "slow" sequence (no qubit pulse)
    machine.gate_set.add_point(
        "initialization",
        voltages={"ch1": level_init[0], "ch2": level_init[1]},
        duration=duration_init,
    )
    machine.gate_set.add_point(
        "idle",
        voltages={"ch1": level_manip[0], "ch2": level_manip[1]},
        duration=duration_manip,
    )
    machine.gate_set.add_point(
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
    with qua.program() as prog:
        a = qua.declare(qua.fixed, value=level_init[0])
        b = qua.declare(qua.fixed, value=level_init[1])
        seq = machine.gate_set.new_sequence()
        seq.step_to_voltages(voltages={"ch1": a, "ch2": b}, duration=duration_init)
        seq.step_to_point("idle")
        seq.step_to_point("readout")
        seq.ramp_to_zero()
    qmm, samples = simulate_program(qmm, machine, prog, simulation_duration=20000)
    validate_program(samples, requested_wf_p, requested_wf_m)


def test_python_voltage_sequence(qmm, machine: QuamGateSet):

    with qua.program() as program:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.1, "ch2": -0.1}, duration=100)
        seq.step_to_voltages(voltages={"ch1": 0.2, "ch2": -0.2}, duration=100)
        seq.step_to_voltages(voltages={"ch1": 0.3, "ch2": -0.3}, duration=100)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

        seq.apply_compensation_pulse(max_voltage=0.3)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

    qmm, samples = simulate_program(qmm, machine, program, int(2e3))
    validate_compensation(samples)


def test_qua_voltage_sequence(qmm, machine: QuamGateSet):

    with qua.program() as program:
        amplitude_1 = qua.declare(qua.fixed, value=0.1)
        amplitude_2 = qua.declare(qua.fixed, value=0.2)
        amplitude_3 = qua.declare(qua.fixed, value=0.3)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(
            voltages={"ch1": amplitude_1, "ch2": -amplitude_1}, duration=100
        )
        seq.step_to_voltages(
            voltages={"ch1": amplitude_2, "ch2": -amplitude_2}, duration=100
        )
        seq.step_to_voltages(
            voltages={"ch1": amplitude_3, "ch2": -amplitude_3}, duration=100
        )
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

        seq.apply_compensation_pulse(max_voltage=0.3)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

    qmm, samples = simulate_program(qmm, machine, program, int(2e3))
    validate_compensation(samples, allowed=10.0)


def test_python_voltage_sequence_zero_comp(qmm, machine: QuamGateSet):

    with qua.program() as program:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.1, "ch2": 0.1}, duration=100)
        seq.step_to_voltages(voltages={"ch1": -0.1, "ch2": -0.1}, duration=100)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

        seq.apply_compensation_pulse(max_voltage=0.3)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

    qmm, samples = simulate_program(qmm, machine, program, int(2e3))
    validate_compensation(samples)


def test_python_voltage_sequence_virtual_gates(
    qmm, virtual_machine: QuamVirtualGateSet
):

    with qua.program() as program:
        seq = virtual_machine.virtual_gate_set.new_sequence(
            track_integrated_voltage=True
        )
        seq.step_to_voltages(voltages={"detuning": 0.1}, duration=100)
        seq.step_to_voltages(voltages={"detuning": 0.2}, duration=100)
        seq.step_to_voltages(voltages={"detuning": 0.3}, duration=100)
        seq.step_to_voltages(voltages={"detuning": 0}, duration=16)

        seq.apply_compensation_pulse(max_voltage=0.3)
        seq.step_to_voltages(voltages={"detuning": 0}, duration=16)

    qmm, samples = simulate_program(qmm, virtual_machine, program, int(2e3))
    validate_compensation(samples)


def test_python_voltage_sequence_virtual_gates_and_elements(
    qmm, virtual_machine: QuamVirtualGateSet
):
    """test that a combination of gates from multiple layers can be combined in step_to_voltages, ramp_to_voltages e.t.c
    example:
    seq.step_to_voltages(voltages={"detuning": 0.1, "ch1":0.2}, duration=100)
    """
    with qua.program() as program:
        seq = virtual_machine.virtual_gate_set.new_sequence(
            track_integrated_voltage=True
        )
        seq.step_to_voltages(voltages={"detuning": 0.1, "ch1": 0.2}, duration=100)
        seq.step_to_voltages(voltages={"detuning": 0, "ch1": 0}, duration=16)

        seq.apply_compensation_pulse(max_voltage=0.3)
        seq.step_to_voltages(voltages={"detuning": 0, "ch1": 0}, duration=16)

    qmm, samples = simulate_program(qmm, virtual_machine, program, int(2e3))
    validate_compensation(samples)
