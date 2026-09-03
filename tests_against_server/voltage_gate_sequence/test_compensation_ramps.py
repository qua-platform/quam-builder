from conftest import QuamGateSet
from qm import qua

from validation_utils import simulate_program, validate_compensation


def test_python_voltage_sequence_ramps(qmm_saas, machine: QuamGateSet):
    """Three Python ramp_to_voltages segments plus a ramp back to 0 V, then
    apply_compensation_pulse. The analog integral on both outputs must be near
    zero, i.e. ramp contributions are included in the compensation calculation."""
    with qua.program() as program:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.ramp_to_voltages(voltages={"ch1": 0.01, "ch2": -0.01}, duration=100, ramp_duration=16)
        seq.ramp_to_voltages(voltages={"ch1": 0.02, "ch2": -0.02}, duration=100, ramp_duration=16)
        seq.ramp_to_voltages(voltages={"ch1": 0.03, "ch2": -0.03}, duration=100, ramp_duration=16)
        seq.ramp_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16, ramp_duration=16)

        seq.apply_compensation_pulse(max_voltage=0.03)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

    _, samples = simulate_program(qmm_saas, machine, program, int(3e3))
    validate_compensation(samples, show_plot=False)


def test_python_ramp_to_point_then_compensation(qmm_saas, machine: QuamGateSet):
    """ramp_to_point uses the named VoltageTuningPoint voltages and its default
    hold duration. After ramping to that point and back to 0 V, compensation
    must cancel the analog integral."""
    machine.gate_set.add_point(
        "manip",
        voltages={"ch1": 0.02, "ch2": -0.02},
        duration=200,
    )
    with qua.program() as program:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.ramp_to_point("manip", ramp_duration=16)
        seq.ramp_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16, ramp_duration=16)
        seq.apply_compensation_pulse(max_voltage=0.03)

    _, samples = simulate_program(qmm_saas, machine, program, int(3e3))
    validate_compensation(samples, show_plot=False)


def test_track_sticky_duration_is_included_in_compensation(qmm_saas, machine: QuamGateSet):
    """After a 100 ns step, a 200 ns QUA wait holds sticky DC while
    track_sticky_duration(200) records that hold in the integral. Compensation
    must then cancel both the played step and the sticky wait, leaving a
    near-zero analog integral."""
    with qua.program() as program:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.02, "ch2": -0.02}, duration=100)
        qua.wait(50)  # 200 ns at 4 ns/cycle; sticky holds the last voltage
        seq.track_sticky_duration(200)
        seq.apply_compensation_pulse(max_voltage=0.03)

    _, samples = simulate_program(qmm_saas, machine, program, int(3e3))
    validate_compensation(samples, show_plot=False)
