from validation_utils import simulate_program, validate_program, validate_compensation
from conftest import QuamGateSet, QuamVirtualGateSet
from qm import qua


def test_python_voltage_sequence_ramps(qmm_saas, machine: QuamGateSet):

    with qua.program() as program:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.ramp_to_voltages(voltages={"ch1": 0.01, "ch2": -0.01}, duration=100, ramp_duration=16)
        seq.ramp_to_voltages(voltages={"ch1": 0.02, "ch2": -0.02}, duration=100, ramp_duration=16)
        seq.ramp_to_voltages(voltages={"ch1": 0.03, "ch2": -0.03}, duration=100, ramp_duration=16)
        seq.ramp_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16, ramp_duration=16)

        seq.apply_compensation_pulse(max_voltage=0.03)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

    _, samples = simulate_program(qmm_saas, machine, program, int(3e3))
    validate_compensation(samples)
