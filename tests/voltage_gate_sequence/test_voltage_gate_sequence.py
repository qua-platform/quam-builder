from qm import qua, generate_qua_script
import pytest

try:
    from quaqsim.program_dict_to_program_compiler.program_tree_builder import (
        ProgramTreeBuilder,
    )
    from quaqsim import program_ast as ast
except ImportError:
    pytest.skip("qua-qsim not installed", allow_module_level=True)


def test_single_pulse_voltage_gate_sequence(machine):
    machine.gate_set.add_point("p1", voltages={"ch1": 0.1, "ch2": 0.2}, duration=100)
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()

        seq.go_to_point("p1")

    program_ast = ProgramTreeBuilder().build(prog)
    assert len(program_ast.body) == 2

    elems = ["ch1", "ch2"]
    amps = [0.4, 0.8]

    for k, play in enumerate(program_ast.body):
        assert isinstance(play, ast.play.Play)
        assert play.element == elems[k]
        assert play.operation == "250mV_square"
        assert int(play.duration.value) == 25

        assert float(play.amp.value) == amps[k]


def test_duplicate_pulse_voltage_gate_sequence(machine):
    """Test that a successive pulse adheres to being sticky (zero amplitude)"""
    machine.gate_set.add_point("p1", voltages={"ch1": 0.1, "ch2": 0.2}, duration=100)
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()

        seq.go_to_point("p1")
        seq.go_to_point("p1")

    program_ast = ProgramTreeBuilder().build(prog)
    assert len(program_ast.body) == 4

    elems = ["ch1", "ch2"] * 2
    amps = [0.4, 0.8, 0, 0]

    for k, play in enumerate(program_ast.body):
        assert isinstance(play, ast.play.Play)
        assert play.element == elems[k]
        assert play.operation == "250mV_square"
        assert int(play.duration.value) == 25

        assert float(play.amp.value) == amps[k]


def test_additional_pulse_voltage_gate_sequence(machine):
    """Test that a successive pulse adheres to being sticky (zero amplitude)"""
    machine.gate_set.add_point("p1", voltages={"ch1": 0.1, "ch2": 0.2}, duration=100)
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence()

        seq.go_to_point("p1")
        seq.go_to_point("p1")

    program_ast = ProgramTreeBuilder().build(prog)
    assert len(program_ast.body) == 4

    elems = ["ch1", "ch2"] * 2
    amps = [0.4, 0.8, 0, 0]

    for k, play in enumerate(program_ast.body):
        assert isinstance(play, ast.play.Play)
        assert play.element == elems[k]
        assert play.operation == "250mV_square"
        assert int(play.duration.value) == 25

        assert float(play.amp.value) == amps[k]
