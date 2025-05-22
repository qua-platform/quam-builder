import pytest

from qm import qua

from quam_builder.architecture.quantum_dots.virtual_gates.virtual_gate_set import (
    VirtualGateSet,
)
from quam_builder.architecture.quantum_dots.voltage_sequence.voltage_sequence import (
    DEFAULT_PULSE_NAME,  # "250mV_square"
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
        seq.go_to_point("virt_p1")

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
        seq.step_to_level(levels={"v_g1": -0.5, "v_g2": 0.2}, duration=80)  # ns

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

        seq.step_to_level(
            levels={"v_g1": qua_v_g1_level, "v_g2": 0.6},
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
            * qua.amp((((0.0 + ((0.5 * exp_qua_v_g1_level) + -0.3)) - 0.0) * 4.0)),
            "ch1",
            duration=30,
        )
        qua.play(
            DEFAULT_PULSE_NAME
            * qua.amp((((0.0 + ((0.0 * exp_qua_v_g1_level) + 0.6)) - 0.0) * 4.0)),
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
        seq.step_to_level(levels={"v_g1": 0.2, "v_g2": 0.1}, duration=40)  # ns
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


# def test_vgs_compensation_after_virtual_step(virtual_gate_set: VirtualGateSet):
#     """Tests apply_compensation_pulse after a virtual gate step.

#     This primarily checks that integrated voltage on physical channels is
#     updated and that compensation pulses are applied to physical channels.
#     """
#     vgs = virtual_gate_set
#     add_default_virtual_layer(vgs)

#     with qua.program() as prog:
#         seq = vgs.new_sequence()
#         seq.step_to_level(levels={"v_g1": 0.25, "v_g2": 0.25}, duration=1000)  # ns
#         seq.apply_compensation_pulse(max_voltage=0.45)

#     # Physical state after step:
#     # v_g1_target = 0.25, v_g2_target = 0.25
#     # ch1_target = 0.5*0.25 - 0.5*0.25 = 0.0 V
#     # ch2_target = 0.0*0.25 + 1.0*0.25 = 0.25 V
#     # amp_ch1_step = 0.0 / 0.25 = 0.0
#     # amp_ch2_step = 0.25 / 0.25 = 1.0
#     # duration_cycles_step = 1000 ns / 4 = 250

#     # Integrated voltage:
#     # ch1: target_voltage=0.0. Contribution to int_V_ch1 is 0.
#     # ch2: target_voltage=0.25. Contribution to int_V_ch2 is positive.
#     # So, ch1 should have no compensation, ch2 should have negative compensation.

#     ast_nodes = ProgramTreeBuilder().build(prog).body
#     play_ops = [node for node in ast_nodes if node.node_type == "PlayStatement"]

#     assert len(play_ops) >= 1

#     ch2_step_found = False
#     ch2_compensation_found = False

#     for op in play_ops:
#         op_target_element = op.qua_object_name
#         op_duration_cycles = op.duration.value

#         if op_target_element == "ch2":
#             if op_duration_cycles == 250 and f"* amp({1.0})" in op.pulse.name:
#                 ch2_step_found = True
#             # Check for a compensation pulse on ch2.
#             # Its duration will be >= MIN_COMPENSATION_DURATION_NS (16ns or 4 cycles)
#             # Its amplitude will be negative.
#             elif op_duration_cycles >= (16 // 4) and f"* amp(-" in op.pulse.name:
#                 ch2_compensation_found = True

#     assert ch2_step_found, "Step pulse for ch2 not found or incorrect."
#     assert ch2_compensation_found, "Compensation pulse for ch2 not found or incorrect."

#     ch1_non_zero_play_found = False
#     for op in play_ops:
#         op_target_element = op.qua_object_name
#         if op_target_element == "ch1":
#             is_zero_amp = False
#             try:  # Check for explicit amp(0.0) or amp(0)
#                 amp_value_str = op.pulse.name.split("amp(")[1].split(")")[0]
#                 if float(amp_value_str) == 0.0:
#                     is_zero_amp = True
#             except (IndexError, ValueError):
#                 pass
#             if not is_zero_amp:  # If not explicitly zero, consider it non-zero play
#                 ch1_non_zero_play_found = True
#                 break

#     assert not ch1_non_zero_play_found, (
#         "ch1 seems to have an unexpected non-zero pulse."
#     )
