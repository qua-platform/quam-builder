"""Analog tests that long sequences break the current volt-time tracker.

Failure modes (see VOLTAGE_SEQUENCE_SPEC: duration may be QUA; compensation
must cancel accumulated volt-time):

- QUA (or Python) duration scaled as ``duration << 16`` overflows signed 32-bit
  for holds longer than 32767 ns, so a 40 µs step stores the wrong area.
- Many QUA-duration steps: each step inserts tracker ``assign``s before play,
  so stretch accumulates along the sequence.
"""

from qm import qua

from validation_utils import (
    simulate_program,
    validate_compensation,
    validate_durations,
    assert_no_interior_gaps,
    SAMPLES_PER_NS,
)


LONG_HOLD_NS = 40_000
# Play 40 µs + compensation ~40 µs + margin.
LONG_SIM_NS = 150_000


def _zero_attenuation(machine):
    for channel in machine.gate_set.channels.values():
        channel.attenuation = 0.0


def test_long_qua_duration_hold_then_compensation(qmm, machine):
    """40 µs at 0.03 V with a QUA duration, then compensate.

    If area tracking wraps, the analog integral after compensation stays large.
    """
    _zero_attenuation(machine)
    level = 0.03
    with qua.program() as program:
        t = qua.declare(int, value=LONG_HOLD_NS)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": level, "ch2": -level}, duration=t)
        seq.apply_compensation_pulse(max_voltage=level)

    _, samples = simulate_program(qmm, machine, program, LONG_SIM_NS)
    validate_compensation(samples, allowed=100.0, show_plot=True)


def test_long_python_duration_qua_voltage_then_compensation(qmm, machine):
    """Same 40 µs hold, but duration is a Python int and the voltage is QUA.
    The tracker still scales duration by 2**16 in the QUA multiply."""
    _zero_attenuation(machine)
    level = 0.03
    with qua.program() as program:
        a = qua.declare(qua.fixed, value=level)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": a, "ch2": -a}, duration=LONG_HOLD_NS)
        seq.apply_compensation_pulse(max_voltage=level)

    _, samples = simulate_program(qmm, machine, program, LONG_SIM_NS)
    validate_compensation(samples, allowed=100.0, show_plot=True)


def test_many_qua_duration_steps_stretch_accumulates(qmm, machine):
    """Twelve 100 ns steps with a QUA duration. Each extra assign-before-play
    lengthens the previous sticky plateau; later steps must still be 100 ns."""
    _zero_attenuation(machine)
    n_steps = 12
    hold_ns = 100
    with qua.program() as program:
        t = qua.declare(int, value=hold_ns)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        for i in range(1, n_steps + 1):
            v = 0.01 * ((i % 4) + 1)
            seq.step_to_voltages(voltages={"ch1": v, "ch2": -v}, duration=t)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

    _, samples = simulate_program(qmm, machine, program, int(8e3))
    expected = [hold_ns * SAMPLES_PER_NS] * n_steps
    for name, sample in samples.con1.analog.items():
        validate_durations(sample, expected, steps=n_steps)
        assert_no_interior_gaps(sample, name)


def test_many_python_steps_then_compensation(qmm, machine):
    """Control: a long chain of Python voltages and Python durations. Area is
    ``duration * voltage_counts`` (no ``<< 16``), so this should still cancel
    today. Contrast with the 40 µs QUA-voltage holds above."""
    _zero_attenuation(machine)
    n_steps = 10
    hold_ns = 2_000
    with qua.program() as program:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        for i in range(n_steps):
            v = 0.02 if i % 2 == 0 else 0.03
            seq.step_to_voltages(voltages={"ch1": v, "ch2": -v}, duration=hold_ns)
        seq.apply_compensation_pulse(max_voltage=0.05)

    sim_ns = n_steps * hold_ns + 50_000
    _, samples = simulate_program(qmm, machine, program, sim_ns)
    validate_compensation(samples, allowed=100.0, show_plot=False)
