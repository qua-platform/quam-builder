"""Analog timing for QUA-variable durations: no stretch, no gaps.

Python-int duration is already covered in test_square_pulses. These cases pass
QUA integers into step/ramp duration (and ramp_duration). Stretch shows up as
plateaus longer than requested; gaps as sub-16 ns dropouts to ~0 V between highs.
Ramps are the usual failure mode (Math.div / wait before the next play).
"""

from qm import qua

from validation_utils import (
    simulate_program,
    validate_durations,
    assert_no_interior_gaps,
    SAMPLES_PER_NS,
)


def _zero_attenuation(machine):
    for channel in machine.gate_set.channels.values():
        channel.attenuation = 0.0


def test_qua_int_duration_two_steps_no_stretch(qmm, machine):
    """step_to_voltages(..., duration=qua_int) must hold each level for exactly
    that many ns (here 200 ns → 400 samples at 2 GS/s)."""
    _zero_attenuation(machine)
    hold_ns = 200
    with qua.program() as program:
        t = qua.declare(int, value=hold_ns)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.02, "ch2": -0.02}, duration=t)
        seq.step_to_voltages(voltages={"ch1": 0.04, "ch2": -0.04}, duration=t)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

    _, samples = simulate_program(qmm, machine, program, int(2e3))
    expected = [hold_ns * SAMPLES_PER_NS] * 2
    for name, sample in samples.con1.analog.items():
        validate_durations(sample, expected, steps=2)
        assert_no_interior_gaps(sample, name)


def test_qua_int_duration_and_qua_voltage_no_stretch(qmm, machine):
    _zero_attenuation(machine)
    hold_ns = 200
    with qua.program() as program:
        t = qua.declare(int, value=hold_ns)
        a = qua.declare(qua.fixed, value=0.02)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": a, "ch2": -a}, duration=t)
        seq.step_to_voltages(voltages={"ch1": 2 * a, "ch2": -2 * a}, duration=t)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

    _, samples = simulate_program(qmm, machine, program, int(2e3))
    expected = [hold_ns * SAMPLES_PER_NS] * 2
    for name, sample in samples.con1.analog.items():
        validate_durations(sample, expected, steps=2)
        assert_no_interior_gaps(sample, name)


def test_qua_ramp_duration_no_gaps_between_ramps(qmm, machine):
    """QUA ramp_duration: successive ramps that never request 0 V must not drop
    to analog zero in between. Hold after each ramp is a Python int."""
    _zero_attenuation(machine)
    ramp_ns = 100
    hold_ns = 100
    with qua.program() as program:
        tr = qua.declare(int, value=ramp_ns)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.ramp_to_voltages(
            voltages={"ch1": 0.03, "ch2": -0.03},
            duration=hold_ns,
            ramp_duration=tr,
        )
        seq.ramp_to_voltages(
            voltages={"ch1": 0.05, "ch2": -0.05},
            duration=hold_ns,
            ramp_duration=tr,
        )
        seq.ramp_to_voltages(
            voltages={"ch1": 0, "ch2": 0}, duration=16, ramp_duration=16
        )

    _, samples = simulate_program(qmm, machine, program, int(3e3))
    for name, sample in samples.con1.analog.items():
        assert_no_interior_gaps(sample, name)


def test_qua_ramp_and_hold_duration_no_gaps(qmm, machine):
    """Both ramp_duration and hold duration are QUA ints."""
    _zero_attenuation(machine)
    ramp_ns = 80
    hold_ns = 160
    with qua.program() as program:
        tr = qua.declare(int, value=ramp_ns)
        th = qua.declare(int, value=hold_ns)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.ramp_to_voltages(
            voltages={"ch1": 0.03, "ch2": -0.03},
            duration=th,
            ramp_duration=tr,
        )
        seq.ramp_to_voltages(
            voltages={"ch1": 0.04, "ch2": -0.04},
            duration=th,
            ramp_duration=tr,
        )
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

    _, samples = simulate_program(qmm, machine, program, int(3e3))
    for name, sample in samples.con1.analog.items():
        assert_no_interior_gaps(sample, name)


def test_qua_duration_in_for_loop_no_gaps(qmm, machine):
    """Duration changes at runtime; analog must not glitch between iterations."""
    _zero_attenuation(machine)
    with qua.program() as program:
        t = qua.declare(int)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        with qua.for_each_(t, [100, 200]):
            seq.step_to_voltages(voltages={"ch1": 0.02, "ch2": -0.02}, duration=t)
            seq.step_to_voltages(voltages={"ch1": 0.03, "ch2": -0.03}, duration=t)
        seq.step_to_voltages(voltages={"ch1": 0, "ch2": 0}, duration=16)

    _, samples = simulate_program(qmm, machine, program, int(4e3))
    for name, sample in samples.con1.analog.items():
        assert_no_interior_gaps(sample, name)
