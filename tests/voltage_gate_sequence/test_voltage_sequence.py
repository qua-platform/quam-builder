from qm import qua
import pytest

try:
    import quaqsim
    from quaqsim.program_dict_to_program_compiler.program_tree_builder import (
        ProgramTreeBuilder,
    )
    from utils import compare_ast_nodes  # type: ignore
except ImportError:
    pytest.skip("qua-qsim not installed", allow_module_level=True)


def test_single_pulse_voltage_sequence(machine):
    machine.gate_set.add_point("p1", voltages={"ch1": 0.1, "ch2": 0.2}, duration=100)
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()

        seq.go_to_point("p1")

    program_ast = ProgramTreeBuilder().build(prog)

    expected_ast = quaqsim.program_ast.program.Program(
        body=[
            quaqsim.program_ast.play.Play(
                amp=quaqsim.program_ast.expressions.literal.Literal(value="0.4"),
                duration=quaqsim.program_ast.expressions.literal.Literal(value="25"),
                element="ch1",
                operation="250mV_square",
            ),
            quaqsim.program_ast.play.Play(
                amp=quaqsim.program_ast.expressions.literal.Literal(value="0.8"),
                duration=quaqsim.program_ast.expressions.literal.Literal(value="25"),
                element="ch2",
                operation="250mV_square",
            ),
        ],
        vars=[],
    )

    assert compare_ast_nodes(program_ast, expected_ast)


def test_duplicate_pulse_voltage_sequence(machine):
    """Test that a successive pulse adheres to being sticky (zero amplitude)"""
    machine.gate_set.add_point("p1", voltages={"ch1": 0.1, "ch2": 0.2}, duration=100)
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()

        seq.go_to_point("p1")
        seq.go_to_point("p1")

    program_ast = ProgramTreeBuilder().build(prog)
    expected_ast = quaqsim.program_ast.program.Program(
        body=[
            quaqsim.program_ast.play.Play(
                amp=quaqsim.program_ast.expressions.literal.Literal(value="0.4"),
                duration=quaqsim.program_ast.expressions.literal.Literal(value="25"),
                element="ch1",
                operation="250mV_square",
            ),
            quaqsim.program_ast.play.Play(
                amp=quaqsim.program_ast.expressions.literal.Literal(value="0.8"),
                duration=quaqsim.program_ast.expressions.literal.Literal(value="25"),
                element="ch2",
                operation="250mV_square",
            ),
            quaqsim.program_ast.play.Play(
                amp=quaqsim.program_ast.expressions.literal.Literal(value="0.0"),
                duration=quaqsim.program_ast.expressions.literal.Literal(value="25"),
                element="ch1",
                operation="250mV_square",
            ),
            quaqsim.program_ast.play.Play(
                amp=quaqsim.program_ast.expressions.literal.Literal(value="0.0"),
                duration=quaqsim.program_ast.expressions.literal.Literal(value="25"),
                element="ch2",
                operation="250mV_square",
            ),
        ],
        vars=[],
    )
    assert compare_ast_nodes(program_ast, expected_ast)


def test_additional_pulse_voltage_sequence(machine):
    """Test that a successive pulse adheres to being sticky (zero amplitude)"""
    machine.gate_set.add_point("p1", voltages={"ch1": 0.1, "ch2": 0.2}, duration=100)
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()

        seq.go_to_point("p1")
        seq.go_to_point("p1")

    program_ast = ProgramTreeBuilder().build(prog)
    expected_ast = quaqsim.program_ast.program.Program(
        body=[
            quaqsim.program_ast.play.Play(
                amp=quaqsim.program_ast.expressions.literal.Literal(value="0.4"),
                duration=quaqsim.program_ast.expressions.literal.Literal(value="25"),
                element="ch1",
                operation="250mV_square",
            ),
            quaqsim.program_ast.play.Play(
                amp=quaqsim.program_ast.expressions.literal.Literal(value="0.8"),
                duration=quaqsim.program_ast.expressions.literal.Literal(value="25"),
                element="ch2",
                operation="250mV_square",
            ),
            quaqsim.program_ast.play.Play(
                amp=quaqsim.program_ast.expressions.literal.Literal(value="0.0"),
                duration=quaqsim.program_ast.expressions.literal.Literal(value="25"),
                element="ch1",
                operation="250mV_square",
            ),
            quaqsim.program_ast.play.Play(
                amp=quaqsim.program_ast.expressions.literal.Literal(value="0.0"),
                duration=quaqsim.program_ast.expressions.literal.Literal(value="25"),
                element="ch2",
                operation="250mV_square",
            ),
        ],
        vars=[],
    )
    assert compare_ast_nodes(program_ast, expected_ast)
