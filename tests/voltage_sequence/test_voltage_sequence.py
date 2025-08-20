from qm import qua
import pytest
from quam_builder.architecture.quantum_dots.exceptions import TimingError
from quam_builder.architecture.quantum_dots.voltage_sequence.constants import (
    DEFAULT_PULSE_NAME,
)

try:
    import quaqsim  # type: ignore
    from quaqsim.program_dict_to_program_compiler.program_tree_builder import (
        ProgramTreeBuilder,
    )
except ImportError:
    pytest.skip("qua-qsim not installed", allow_module_level=True)

from test_utils import compare_ast_nodes, print_ast_as_code  # type: ignore

# # Extract the AST as a string
# from utils import ast_to_code_string
# import pyperclip
# code = ast_to_code_string(ast)
# pyperclip.copy(f"expected_ast = {code}")
# print(code)

# # Extract the QUA program as a string
# from qm import generate_qua_script
# print(generate_qua_script(prog, config=None))


def test_invalid_timing_multiple_4(machine):
    machine.gate_set.add_point("p1", voltages={"ch1": 0.1, "ch2": 0.2}, duration=41)
    with qua.program() as _prog:  # noqa: F841
        seq = machine.gate_set.new_sequence()
        with pytest.raises(TimingError):
            seq.go_to_point("p1")


def test_invalid_timing_min_duration(machine):
    machine.gate_set.add_point("p1", voltages={"ch1": 0.1, "ch2": 0.2}, duration=12)
    with qua.program() as _prog:  # noqa: F841
        seq = machine.gate_set.new_sequence()
        with pytest.raises(TimingError):
            seq.go_to_point("p1")


def test_go_to_single_point(machine):
    """Tests stepping to a single predefined point."""
    machine.gate_set.add_point("p1", voltages={"ch1": 0.1, "ch2": 0.2}, duration=100)
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.go_to_point("p1")
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.4), "ch1", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.8), "ch2", duration=25)
    expected_ast = ProgramTreeBuilder().build(expected_program)

    assert compare_ast_nodes(ast, expected_ast)


def test_go_to_multiple_points(machine):
    """Tests stepping to two different points sequentially."""
    machine.gate_set.add_point("p1", voltages={"ch1": 0.1, "ch2": 0.2}, duration=100)
    machine.gate_set.add_point("p2", voltages={"ch1": 0.3, "ch2": 0.4}, duration=200)
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.go_to_point("p1")
        seq.go_to_point("p2")
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.4), "ch1", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.8), "ch2", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.8), "ch1", duration=50)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.8), "ch2", duration=50)
    expected_ast = ProgramTreeBuilder().build(expected_program)

    assert compare_ast_nodes(ast, expected_ast)


def test_go_to_point_with_custom_duration(machine):
    """Tests overriding the point's default duration in go_to_point."""
    machine.gate_set.add_point(
        "p1", voltages={"ch1": 0.1}, duration=100
    )  # Default duration
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.go_to_point("p1", duration=60)
        seq.go_to_point("p1")
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.4), "ch1", duration=15)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.0), "ch2", duration=15)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.0), "ch1", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.0), "ch2", duration=25)
    expected_ast = ProgramTreeBuilder().build(expected_program)

    assert compare_ast_nodes(ast, expected_ast)


def test_step_to_level_single_channel(machine):
    """Tests stepping a single channel to a specified voltage level."""
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.step_to_level(levels={"ch1": 0.25}, duration=120)
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(1.0), "ch1", duration=30)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.0), "ch2", duration=30)
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_step_to_level_multiple_channels(machine):
    """Tests stepping multiple channels to specified voltage levels simultaneously."""
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.step_to_level(levels={"ch1": 0.15, "ch2": -0.1}, duration=160)
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.6), "ch1", duration=40)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(-0.4), "ch2", duration=40)
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_step_to_level_then_go_to_point(machine):
    """Tests a step_to_level operation followed by a go_to_point."""
    machine.gate_set.add_point(
        "p_after_step", voltages={"ch1": 0.2, "ch2": 0.2}, duration=80
    )
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.step_to_level(levels={"ch1": 0.1}, duration=100)
        seq.go_to_point("p_after_step")

    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.4), "ch1", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.0), "ch2", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.4), "ch1", duration=20)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.8), "ch2", duration=20)
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_sequence_with_qua_variable_duration_step_to_level(machine):
    """Tests using a QUA variable for duration in step_to_level."""
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=False)
        qua_duration = qua.declare(int)
        qua.assign(qua_duration, 200)  # ns
        seq.step_to_level(levels={"ch1": 0.2}, duration=qua_duration)
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        expected_qua_duration = qua.declare(int)
        qua.assign(expected_qua_duration, 200)
        qua.play(
            DEFAULT_PULSE_NAME * qua.amp(0.8),
            "ch1",
            duration=expected_qua_duration >> 2,
        )
        qua.play(
            DEFAULT_PULSE_NAME * qua.amp(0.0),
            "ch2",
            duration=expected_qua_duration >> 2,
        )
    expected_ast = ProgramTreeBuilder().build(expected_program)

    assert compare_ast_nodes(ast, expected_ast)


def test_sequence_with_qua_variable_voltage_step_to_level(machine):
    """Tests using a QUA variable for voltage in step_to_level."""
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=False)
        qua_voltage = qua.declare(qua.fixed)
        qua.assign(qua_voltage, 0.15)
        seq.step_to_level(levels={"ch1": qua_voltage, "ch2": 0.1}, duration=100)
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        expected_qua_voltage = qua.declare(qua.fixed)
        qua.assign(expected_qua_voltage, 0.15)
        qua.play(
            DEFAULT_PULSE_NAME * qua.amp((expected_qua_voltage - 0.0) << 2),
            "ch1",
            duration=25,
        )
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.4), "ch2", duration=25)
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_ramp_to_zero_immediate(machine):
    """Tests ramp_to_zero with no duration (immediate QUA ramp_to_zero)."""
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.step_to_level(levels={"ch1": 0.2, "ch2": -0.15}, duration=100)
        seq.ramp_to_zero()  # Uses QUA's ramp_to_zero(element_name)
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.8), "ch1", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(-0.6), "ch2", duration=25)
        qua.ramp_to_zero("ch1")
        qua.ramp_to_zero("ch2")

    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_ramp_to_zero_with_duration(machine):
    """Tests ramp_to_zero with a specified ramp duration."""
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.step_to_level(levels={"ch1": 0.25}, duration=100)
        seq.ramp_to_zero(ramp_duration_ns=200)
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(1.0), "ch1", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.0), "ch2", duration=25)
        qua.play(qua.ramp(-0.25 / 200), "ch1", duration=50)
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_ramp_to_zero_with_duration_multiple_channels(machine):
    """Tests ramp_to_zero with a specified ramp duration."""
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()
        seq.step_to_level(levels={"ch1": 0.25}, duration=100)
        seq.step_to_level(levels={"ch1": 0.25, "ch2": 0.25}, duration=100)
        seq.ramp_to_zero(ramp_duration_ns=200)
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(1.0), "ch1", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.0), "ch2", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.0), "ch1", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(1.0), "ch2", duration=25)
        qua.play(qua.ramp(-0.25 / 200), "ch1", duration=50)
        qua.play(qua.ramp(-0.25 / 200), "ch2", duration=50)
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


# def test_apply_compensation_pulse_from_zero_integrated_voltage(machine):
#     """Tests apply_compensation_pulse when integrated voltage is zero."""
#     with qua.program() as prog:
#         seq = machine.gate_set.new_sequence()
#         # No prior operations, so integrated voltage is zero for all channels.
#         seq.apply_compensation_pulse(max_voltage=0.4)
#     # ast = ProgramTreeBuilder().build(prog)
#     # Expected AST: Should be empty or only contain QUA variable declarations
#     # if _calculate_qua_compensation_params is called, but no play commands.


# More complex compensation tests would involve setting up non-zero integrated voltages
# and verifying the calculated compensation pulse amplitudes and durations.
# For example:
# def test_apply_compensation_pulse_with_positive_integrated_voltage(machine):
#     with qua.program() as prog:
#         seq = machine.gate_set.new_sequence()
#         seq.step_to_level(levels={"ch1": 0.1}, duration=1000) # Positive integrated_v
#         seq.apply_compensation_pulse(max_voltage=0.4)
#     # ast = ProgramTreeBuilder().build(prog)
#     # Expected AST: step_to_level, then a negative pulse on ch1 for compensation.

# def test_apply_compensation_pulse_with_qua_vars(machine):
#     with qua.program() as prog:
#         seq = machine.gate_set.new_sequence()
#         qua_level = qua.declare(qua.fixed, value=0.05)
#         qua_dur = qua.declare(int, value=2000) #ns
#         seq.step_to_level(levels={"ch1": qua_level}, duration=qua_dur)
#         seq.apply_compensation_pulse(max_voltage=0.4)
#     # ast = ProgramTreeBuilder().build(prog)
#     # Expected AST: QUA assignments, step_to_level, then QUA logic for compensation.
