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
