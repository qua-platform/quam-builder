"""Tests for QuantumDotPair.

All objects are real — no mocks or stubs.
"""

from qm import qua

from quam_builder.architecture.quantum_dots.components import (
    QuantumDot,
    SensorDot,
    BarrierGate,
)


class TestQuantumDotPairProperties:
    def test_quantum_dots_linked(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert len(pair.quantum_dots) == 2
        assert all(isinstance(qd, QuantumDot) for qd in pair.quantum_dots)

    def test_sensor_dots_linked(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert len(pair.sensor_dots) >= 1
        assert all(isinstance(sd, SensorDot) for sd in pair.sensor_dots)

    def test_barrier_gate_linked(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert isinstance(pair.barrier_gate, BarrierGate)

    def test_name_equals_id(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert pair.name == "dot1_dot2_pair"

    def test_voltage_sequence_accessible(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        vs = pair.voltage_sequence
        assert vs is not None

    def test_machine_reference(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert pair.machine is qd_machine


class TestDetuningAxis:
    def test_detuning_axis_name_set(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        assert pair.detuning_axis_name == "dot1_dot2_epsilon"

    def test_detuning_axis_in_virtual_gate_set(self, qd_machine):
        vgs = qd_machine.virtual_gate_sets["main_qpu"]
        assert "dot1_dot2_epsilon" in vgs.valid_channel_names

    def test_two_detuning_axes_coexist(self, qd_machine):
        vgs = qd_machine.virtual_gate_sets["main_qpu"]
        assert "dot1_dot2_epsilon" in vgs.valid_channel_names
        assert "dot3_dot4_epsilon" in vgs.valid_channel_names


class TestDetuningControl:
    def test_go_to_detuning_in_qua(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        with qua.program() as prog:
            pair.go_to_detuning(0.3)
        assert prog is not None

    def test_step_to_detuning_in_qua(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        with qua.program() as prog:
            pair.step_to_detuning(0.5, duration=100)
        assert prog is not None

    def test_ramp_to_detuning_in_qua(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        with qua.program() as prog:
            pair.ramp_to_detuning(0.5, ramp_duration=20, duration=100)
        assert prog is not None


class TestQuantumDotPairVoltagePoints:
    def test_add_point(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        full_name = pair.add_point(
            "symmetric",
            voltages={"virtual_dot_1": 0.1, "virtual_dot_2": 0.1},
            duration=100,
        )
        macros = pair.voltage_sequence.gate_set.get_macros()
        assert full_name in macros

    def test_step_to_point_in_qua(self, qd_machine):
        pair = qd_machine.quantum_dot_pairs["dot1_dot2_pair"]
        pair.add_point(
            "sym",
            voltages={"virtual_dot_1": 0.1, "virtual_dot_2": 0.1},
            duration=100,
        )
        with qua.program() as prog:
            pair.step_to_point("sym")
        assert prog is not None
