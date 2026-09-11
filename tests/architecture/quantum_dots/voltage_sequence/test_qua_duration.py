"""Compile-time coverage for QUA integer durations (no analog / no qsim).

Existing AST tests in test_voltage_sequence.py use enforce_qua_calcs=False and
track_integrated_voltage=False. These use the default tracking path.
"""

from qm import generate_qua_script, qua


def test_script_step_uses_qua_duration_shift(machine):
    with qua.program() as prog:
        t = qua.declare(int, value=200)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": 0.1, "ch2": 0.1}, duration=t)
    script = generate_qua_script(prog, config=None)
    assert ">> 2" in script or ">>2" in script.replace(" ", "")
    assert "play(" in script


def test_script_ramp_uses_math_div_for_qua_ramp_duration(machine):
    with qua.program() as prog:
        tr = qua.declare(int, value=80)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.ramp_to_voltages(
            voltages={"ch1": 0.2, "ch2": 0.1}, duration=160, ramp_duration=tr
        )
    script = generate_qua_script(prog, config=None)
    assert "Math.div" in script
    assert "ramp(" in script


def test_script_ramp_qua_hold_duration_waits(machine):
    with qua.program() as prog:
        th = qua.declare(int, value=160)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.ramp_to_voltages(
            voltages={"ch1": 0.2, "ch2": 0.1}, duration=th, ramp_duration=80
        )
    script = generate_qua_script(prog, config=None)
    assert "wait(" in script
    assert ">> 2" in script or ">>2" in script.replace(" ", "")


def test_script_qua_duration_and_qua_voltage(machine):
    with qua.program() as prog:
        t = qua.declare(int, value=100)
        v = qua.declare(qua.fixed, value=0.1)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": v, "ch2": -v}, duration=t)
    script = generate_qua_script(prog, config=None)
    assert "play(" in script
    assert ">> 2" in script or ">>2" in script.replace(" ", "")


SIGNED_I32_MAX = 2**31 - 1
# QUA int is signed 32-bit. Scaling duration by 2**16 overflows for holds
# longer than 32767 ns (40 µs is a typical "slow" DC step).
LONG_HOLD_NS = 40_000


def test_script_long_qua_duration_must_not_shift_duration_by_16(machine):
    """Area tracking must not do `duration << 16` in QUA: 40000 << 16 does not
    fit in a signed 32-bit int, so accumulated volt-time wraps and compensation
    is wrong."""
    assert LONG_HOLD_NS << 16 > SIGNED_I32_MAX
    with qua.program() as prog:
        t = qua.declare(int, value=LONG_HOLD_NS)
        v = qua.declare(qua.fixed, value=0.1)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": v, "ch2": v}, duration=t)
    script = generate_qua_script(prog, config=None).replace(" ", "")
    assert "<<16" not in script and "*65536" not in script, (
        "duration << 16 overflows signed 32-bit QUA int for long holds; "
        "use a split multiply that keeps intermediates in range"
    )


def test_script_long_python_duration_qua_voltage_must_not_embed_overflow_literal(
    machine,
):
    """Python duration with a QUA voltage still must not bake `duration << 16`
    into the program as a 32-bit literal."""
    overflow_literal = LONG_HOLD_NS << 16
    wrapped = overflow_literal - (1 << 32)  # if the compiler truncates
    with qua.program() as prog:
        v = qua.declare(qua.fixed, value=0.1)
        seq = machine.gate_set.new_sequence(track_integrated_voltage=True)
        seq.step_to_voltages(voltages={"ch1": v, "ch2": v}, duration=LONG_HOLD_NS)
    script = generate_qua_script(prog, config=None).replace(" ", "")
    assert str(overflow_literal) not in script
    assert str(wrapped) not in script
