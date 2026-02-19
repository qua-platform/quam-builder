"""Tests for LDQubitPair.

All objects are real — no mocks or stubs.
"""

from qm import qua

from quam_builder.architecture.quantum_dots.components import QuantumDotPair
from quam_builder.architecture.quantum_dots.qubit import LDQubit


class TestLDQubitPairProperties:
    def test_qubit_control_and_target(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        assert isinstance(pair.qubit_control, LDQubit)
        assert isinstance(pair.qubit_target, LDQubit)
        assert pair.qubit_control is qd_machine.qubits["Q1"]
        assert pair.qubit_target is qd_machine.qubits["Q2"]

    def test_quantum_dot_pair_linked(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        assert isinstance(pair.quantum_dot_pair, QuantumDotPair)

    def test_detuning_axis_name(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        assert pair.detuning_axis_name == "dot1_dot2_epsilon"

    def test_voltage_sequence_accessible(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        assert pair.voltage_sequence is not None

    def test_machine_reference(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        assert pair.machine is qd_machine

    def test_physical_channel(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        assert pair.physical_channel is pair.quantum_dot_pair.physical_channel


class TestLDQubitPairVoltageOps:
    def test_add_point(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        full_name = pair.add_point("exchange", {"dot1_dot2_epsilon": 0.5}, duration=100)
        macros = pair.voltage_sequence.gate_set.get_macros()
        assert full_name in macros

    def test_step_to_point_in_qua(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        pair.add_point("exchange", {"dot1_dot2_epsilon": 0.5}, duration=100)

        with qua.program() as prog:
            pair.step_to_point("exchange")

        assert prog is not None

    def test_ramp_to_point_in_qua(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        pair.add_point("ramp_target", {"dot1_dot2_epsilon": 0.3}, duration=100)

        with qua.program() as prog:
            pair.ramp_to_point("ramp_target", ramp_duration=20)

        assert prog is not None


class TestLDQubitPairFluentAPI:
    def test_with_step_point_returns_self(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        result = pair.with_step_point("idle", voltages={"dot1_dot2_epsilon": 0.0}, duration=100)
        assert result is pair

    def test_chained_operations(self, qd_machine):
        pair = qd_machine.qubit_pairs["Q1_Q2"]
        result = pair.with_step_point(
            "idle", voltages={"dot1_dot2_epsilon": 0.0}, duration=100
        ).with_step_point("exchange", voltages={"dot1_dot2_epsilon": 0.5}, duration=200)
        assert result is pair
        assert "idle" in pair.macros
        assert "exchange" in pair.macros


class TestMultiplePairs:
    def test_two_pairs_are_independent(self, qd_machine):
        p1 = qd_machine.qubit_pairs["Q1_Q2"]
        p2 = qd_machine.qubit_pairs["Q3_Q4"]

        assert p1.detuning_axis_name != p2.detuning_axis_name
        assert p1.quantum_dot_pair is not p2.quantum_dot_pair
