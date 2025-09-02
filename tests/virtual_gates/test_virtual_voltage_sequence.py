import pytest

from qm import qua

from quam_builder.architecture.quantum_dots.virtual_gates.virtual_gate_set import (
    VirtualGateSet,
)
from quam_builder.architecture.quantum_dots.voltage_sequence.voltage_sequence import (
    DEFAULT_PULSE_NAME,  # DEFAULT_PULSE_NAME
)
from test_utils import compare_ast_nodes, print_ast_as_code

try:
    from quaqsim.program_dict_to_program_compiler.program_tree_builder import (
        ProgramTreeBuilder,
    )
except ImportError:
    pytest.skip(
        "qua-qsim or comparison utilities not found, skipping AST comparison tests",
        allow_module_level=True,
    )


def add_default_virtual_layer(vgs: VirtualGateSet):
    """Adds the default virtual layer used in these tests.

    Layer: v_g1, v_g2 -> ch1, ch2
    Matrix M = [[2.0, 1.0], [0.0, 1.0]]
    Inverse M_inv = [[0.5, -0.5], [0.0, 1.0]]
    """
    vgs.add_layer(
        source_gates=["v_g1", "v_g2"],
        target_gates=["ch1", "ch2"],  # These must match keys in vgs.channels
        matrix=[[2.0, 1.0], [0.0, 1.0]],
    )


def test_vgs_go_to_virtual_point(virtual_gate_set: VirtualGateSet):
    """Tests stepping to a predefined point with virtual gate voltages."""
    vgs = virtual_gate_set
    add_default_virtual_layer(vgs)

    vgs.add_point(
        name="virt_p1",
        voltages={"v_g1": 1.0, "v_g2": 0.4},
        duration=100,  # ns
    )

    with qua.program() as prog:
        seq = vgs.new_sequence()
        seq.step_to_point("virt_p1")

    # Calculate expected physical voltages (assuming initial state is 0V for ch1, ch2)
    # v_g1_target = 1.0, v_g2_target = 0.4
    # ch1_target = 0.5*1.0 - 0.5*0.4 = 0.5 - 0.2 = 0.3 V
    # ch2_target = 0.0*1.0 + 1.0*0.4 = 0.4 V
    # amp_ch1 = 0.3 / 0.25 = 1.2
    # amp_ch2 = 0.4 / 0.25 = 1.6
    # duration_cycles = 100 ns / 4 ns/cycle = 25

    ast = ProgramTreeBuilder().build(prog)
    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(1.2), "ch1", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(1.6), "ch2", duration=25)
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_vgs_step_to_virtual_level(virtual_gate_set: VirtualGateSet):
    """Tests stepping to specified virtual voltage levels."""
    vgs = virtual_gate_set
    add_default_virtual_layer(vgs)

    with qua.program() as prog:
        seq = vgs.new_sequence()
        seq.step_to_voltages(voltages={"v_g1": -0.5, "v_g2": 0.2}, duration=80)  # ns

    # Calculate expected physical voltages (initial state 0V)
    # v_g1_target = -0.5, v_g2_target = 0.2
    # ch1_target = 0.5*(-0.5) - 0.5*0.2 = -0.25 - 0.1 = -0.35 V
    # ch2_target = 0.0*(-0.5) + 1.0*0.2 = 0.2 V
    # amp_ch1 = -0.35 / 0.25 = -1.4
    # amp_ch2 = 0.2 / 0.25 = 0.8
    # duration_cycles = 80 ns / 4 = 20

    ast = ProgramTreeBuilder().build(prog)
    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(-1.4), "ch1", duration=20)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.8), "ch2", duration=20)
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_vgs_step_to_virtual_level_qua_voltage(virtual_gate_set: VirtualGateSet):
    """Tests stepping to virtual levels with one level being a QUA variable."""
    vgs = virtual_gate_set
    add_default_virtual_layer(vgs)

    with qua.program() as prog:
        seq = vgs.new_sequence(track_integrated_voltage=False)
        qua_v_g1_level = qua.declare(qua.fixed)
        qua.assign(qua_v_g1_level, 0.8)  # Target for v_g1

        seq.step_to_voltages(
            voltages={"v_g1": qua_v_g1_level, "v_g2": 0.6},
            duration=120,  # ns
        )

    # Expected physical targets (initial state 0V):
    # v_g1_target_qua = qua_v_g1_level (0.8)
    # v_g2_target_py = 0.6
    # ch1_target_qua = 0.5*qua_v_g1_level - 0.5*0.6
    # ch2_target_qua = 1.0*0.6
    # amp_ch1_qua = (0.5*qua_v_g1_level - 0.3) / 0.25 = 2.0*qua_v_g1_level - 1.2
    # amp_ch2_const = (0.6) / 0.25 = 2.4
    # duration_cycles = 120 ns / 4 = 30

    ast = ProgramTreeBuilder().build(prog)
    with qua.program() as expected_program:
        exp_qua_v_g1_level = qua.declare(qua.fixed)
        qua.assign(exp_qua_v_g1_level, 0.8)

        qua.play(
            DEFAULT_PULSE_NAME
            * qua.amp((((0.0 + ((0.5 * exp_qua_v_g1_level) + -0.3)) - 0.0) << 2)),
            "ch1",
            duration=30,
        )
        qua.play(
            DEFAULT_PULSE_NAME
            * qua.amp((((0.0 + ((0.0 * exp_qua_v_g1_level) + 0.6)) - 0.0) << 2)),
            "ch2",
            duration=30,
        )

    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_vgs_ramp_to_zero_after_virtual_step(virtual_gate_set: VirtualGateSet):
    """Tests ramp_to_zero after operations on virtual gates."""
    vgs = virtual_gate_set
    add_default_virtual_layer(vgs)

    with qua.program() as prog:
        seq = vgs.new_sequence()
        seq.step_to_voltages(voltages={"v_g1": 0.2, "v_g2": 0.1}, duration=40)  # ns
        seq.ramp_to_zero()

    # Physical state after step:
    # v_g1_target = 0.2, v_g2_target = 0.1
    # ch1_target = 0.5*0.2 - 0.5*0.1 = 0.1 - 0.05 = 0.05 V
    # ch2_target = 0.0*0.2 + 1.0*0.1 = 0.1 V
    # amp_ch1_step = 0.05 / 0.25 = 0.2
    # amp_ch2_step = 0.1 / 0.25 = 0.4
    # duration_cycles_step = 40 ns / 4 = 10

    ast = ProgramTreeBuilder().build(prog)
    with qua.program() as expected_program:
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.2), "ch1", duration=10)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.4), "ch2", duration=10)
        qua.ramp_to_zero("ch1")
        qua.ramp_to_zero("ch2")
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_ramp_to_voltages_simple(machine):
    """Tests a simple ramp_to_voltages operation."""
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=False)
        seq.ramp_to_voltages(
            voltages={"ch1": 0.2, "ch2": -0.1},
            duration=120,
            ramp_duration=40,  # ns
        )
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        # ch1: 0.0 -> 0.2 (delta=0.2), ramp=40 (10 cycles), hold=120 (30 cycles)
        # ch2: 0.0 -> -0.1 (delta=-0.1), ramp=40 (10 cycles), hold=120 (30 cycles)
        qua.play(qua.ramp(0.2 / 40.0), "ch1", duration=10)
        qua.wait(30, "ch1")
        qua.play(qua.ramp(-0.1 / 40.0), "ch2", duration=10)
        qua.wait(30, "ch2")
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_ramp_to_point_simple(machine):
    """Tests a simple ramp_to_point operation."""
    machine.gate_set.add_point(
        "p_ramp", voltages={"ch1": 0.15, "ch2": 0.05}, duration=200
    )
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=False)
        seq.ramp_to_point("p_ramp", ramp_duration=80)
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        # ch1: 0.0 -> 0.15 (delta=0.15), ramp=80 (20 cycles), hold=200 (50 cycles)
        # ch2: 0.0 -> 0.05 (delta=0.05), ramp=80 (20 cycles), hold=200 (50 cycles)
        qua.play(qua.ramp(0.15 / 80.0), "ch1", duration=20)
        qua.wait(50, "ch1")
        qua.play(qua.ramp(0.05 / 80.0), "ch2", duration=20)
        qua.wait(50, "ch2")
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_step_then_ramp(machine):
    """Tests a step operation followed by a ramp operation."""
    machine.gate_set.add_point(
        "p_step", voltages={"ch1": 0.1, "ch2": 0.1}, duration=100
    )
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=False)
        seq.step_to_point("p_step")  # Current level: ch1=0.1, ch2=0.1
        seq.ramp_to_voltages(
            voltages={"ch1": 0.3, "ch2": -0.1}, duration=160, ramp_duration=80
        )
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        # Go to point p_step (0.1, 0.1), duration 100ns (25 cycles)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.4), "ch1", duration=25)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(0.4), "ch2", duration=25)
        # Ramp to level (0.3, -0.1), ramp=80ns (20 cycles), hold=160ns (40 cycles)
        # ch1: 0.1 -> 0.3 (delta=0.2)
        # ch2: 0.1 -> -0.1 (delta=-0.2)
        qua.play(qua.ramp(0.2 / 80.0), "ch1", duration=20)
        qua.wait(40, "ch1")
        qua.play(qua.ramp(-0.2 / 80.0), "ch2", duration=20)
        qua.wait(40, "ch2")
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_ramp_then_step(machine):
    """Tests a ramp operation followed by a step operation."""
    machine.gate_set.add_point(
        "p_final", voltages={"ch1": 0.05, "ch2": -0.05}, duration=500
    )
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=False)
        seq.ramp_to_voltages(
            voltages={"ch1": 0.2, "ch2": 0.2}, duration=100, ramp_duration=40
        )  # Current level: ch1=0.2, ch2=0.2
        seq.step_to_point("p_final")
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        # Ramp to level (0.2, 0.2), ramp=40ns (10 cycles), hold=100ns (25 cycles)
        qua.play(qua.ramp(0.2 / 40.0), "ch1", duration=10)
        qua.wait(25, "ch1")
        qua.play(qua.ramp(0.2 / 40.0), "ch2", duration=10)
        qua.wait(25, "ch2")
        # Go to point (0.05, -0.05), duration 500ns (125 cycles)
        # ch1: 0.2 -> 0.05 (delta=-0.15) -> amp = -0.15 / 0.25 = -0.6
        # ch2: 0.2 -> -0.05 (delta=-0.25) -> amp = -0.25 / 0.25 = -1.0
        qua.play(DEFAULT_PULSE_NAME * qua.amp(-0.6), "ch1", duration=125)
        qua.play(DEFAULT_PULSE_NAME * qua.amp(-1.0), "ch2", duration=125)
    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_ramp_to_voltages_with_qua_voltage(machine):
    """Tests ramp_to_voltages using a QUA variable for the voltage level."""
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=False)
        qua_level = qua.declare(qua.fixed)
        qua.assign(qua_level, 0.15)
        seq.ramp_to_voltages(
            voltages={"ch1": qua_level, "ch2": 0.1}, duration=100, ramp_duration=40
        )
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        expected_qua_level = qua.declare(qua.fixed)  # v1
        _vseq_tmp_ch1_ramp_rate = qua.declare(qua.fixed)  # v2
        qua.assign(expected_qua_level, 0.15)
        # ch1: 0.0 -> qua_level (0.15), ramp=40(10), hold=100(25)
        # ch2: 0.0 -> 0.1 (delta=0.1), ramp=40(10), hold=100(25)
        qua.assign(
            _vseq_tmp_ch1_ramp_rate,
            (expected_qua_level - 0.0) * qua.Math.div(1.0, 40.0),
        )
        qua.play(qua.ramp(_vseq_tmp_ch1_ramp_rate), "ch1", duration=10)
        qua.wait(25, "ch1")
        qua.play(qua.ramp(0.25 / 100), "ch2", duration=10)
        qua.wait(25, "ch2")

    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)


def test_ramp_to_voltages_with_qua_ramp_duration(machine):
    """Tests ramp_to_voltages using a QUA variable for the ramp duration."""
    with qua.program() as prog:
        seq = machine.gate_set.new_sequence(track_integrated_voltage=False)
        qua_ramp_dur = qua.declare(int)
        qua.assign(qua_ramp_dur, 80)  # ns
        seq.ramp_to_voltages(
            voltages={"ch1": 0.2}, duration=160, ramp_duration=qua_ramp_dur
        )
    ast = ProgramTreeBuilder().build(prog)

    with qua.program() as expected_program:
        expected_qua_ramp_dur = qua.declare(int)
        _vseq_tmp_ch1_ramp_rate = qua.declare(qua.fixed)
        _vseq_tmp_ch2_ramp_rate = qua.declare(qua.fixed)
        qua.assign(expected_qua_ramp_dur, 80)
        # ch1: 0.0 -> 0.2 (delta=0.2), ramp=80(20), hold=160(40) -> 40
        # ch2: 0.0 -> 0.0 (delta=0.0), ramp=80(20), hold=160(40) -> 40
        qua.assign(
            _vseq_tmp_ch1_ramp_rate, 0.2 * qua.Math.div(1.0, expected_qua_ramp_dur)
        )
        qua.play(
            qua.ramp(_vseq_tmp_ch1_ramp_rate),
            "ch1",
            duration=expected_qua_ramp_dur >> 2,
        )
        qua.wait(40, "ch1")
        qua.assign(
            _vseq_tmp_ch2_ramp_rate, 0.0 * qua.Math.div(1.0, expected_qua_ramp_dur)
        )
        qua.play(
            qua.ramp(_vseq_tmp_ch2_ramp_rate),
            "ch2",
            duration=expected_qua_ramp_dur >> 2,
        )
        qua.wait(40, "ch2")

    expected_ast = ProgramTreeBuilder().build(expected_program)
    assert compare_ast_nodes(ast, expected_ast)
