"""Tests for BarrierGate.

All objects are real — no mocks or stubs.
"""

from qm import qua

from quam_builder.architecture.quantum_dots.components import BarrierGate


class TestBarrierGateProperties:
    def test_barrier_gates_exist(self, qd_machine):
        assert len(qd_machine.barrier_gates) == 3

    def test_barrier_gate_type(self, qd_machine):
        for bg in qd_machine.barrier_gates.values():
            assert isinstance(bg, BarrierGate)

    def test_barrier_gate_has_physical_channel(self, qd_machine):
        for bg in qd_machine.barrier_gates.values():
            assert bg.physical_channel is not None

    def test_name_equals_id(self, qd_machine):
        for bg in qd_machine.barrier_gates.values():
            assert bg.name == bg.id

    def test_machine_reference(self, qd_machine):
        bg = list(qd_machine.barrier_gates.values())[0]
        assert bg.machine is qd_machine

    def test_current_voltage_default(self, qd_machine):
        for bg in qd_machine.barrier_gates.values():
            assert bg.current_voltage == 0.0

    def test_voltage_sequence_accessible(self, qd_machine):
        bg = list(qd_machine.barrier_gates.values())[0]
        assert bg.voltage_sequence is not None


class TestBarrierGateVoltageOps:
    def test_update_current_voltage(self, qd_machine):
        bg = list(qd_machine.barrier_gates.values())[0]
        bg._update_current_voltage(0.35)
        assert bg.current_voltage == 0.35

    def test_add_point(self, qd_machine):
        bg = list(qd_machine.barrier_gates.values())[0]
        full_name = bg.add_point("open", {bg.id: 0.5}, duration=100)
        macros = bg.voltage_sequence.gate_set.get_macros()
        assert full_name in macros

    def test_step_to_point_in_qua(self, qd_machine):
        bg = list(qd_machine.barrier_gates.values())[0]
        bg.add_point("open", {bg.id: 0.5}, duration=100)
        with qua.program() as prog:
            bg.step_to_point("open")
        assert prog is not None


class TestBarrierGateInPair:
    def test_pair_barrier_gate(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert isinstance(pair.barrier_gate, BarrierGate)
        assert pair.barrier_gate in qd_machine.barrier_gates.values()
