"""Tests for LDQubit (Loss DiVincenzo spin qubit).

All objects are real — no mocks or stubs.
"""

from qm import qua

from quam_builder.architecture.quantum_dots.components import QuantumDot


class TestLDQubitProperties:
    def test_physical_channel(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert qubit.physical_channel is qubit.quantum_dot.physical_channel

    def test_machine_reference(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert qubit.machine is qd_machine

    def test_voltage_sequence(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert qubit.voltage_sequence is qubit.quantum_dot.voltage_sequence

    def test_quantum_dot_is_real(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert isinstance(qubit.quantum_dot, QuantumDot)

    def test_xy_channel_none_by_default(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert qubit.xy_channel is None


class TestThermalizationTime:
    def test_default_when_T1_is_none(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        assert qubit.T1 is None
        therm = qubit.thermalization_time
        assert therm == 50_000

    def test_calculated_from_T1(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        qubit.T1 = 1e-6  # 1 µs
        expected = round(5 * 1e-6 * 1e9 / 4) * 4
        assert qubit.thermalization_time == expected


class TestVoltageOperations:
    def test_add_point(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        full_name = qubit.add_point("idle", {"virtual_dot_1": 0.1}, duration=100)
        macros = qubit.quantum_dot.voltage_sequence.gate_set.get_macros()
        assert full_name in macros

    def test_step_to_point_in_qua(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        qubit.add_point("idle", {"virtual_dot_1": 0.1}, duration=100)

        with qua.program() as prog:
            qubit.step_to_point("idle")

        assert prog is not None

    def test_add_point_with_step_macro(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        qubit.add_point_with_step_macro("load", voltages={"virtual_dot_1": 0.2}, duration=200)
        assert "load" in qubit.macros

    def test_ramp_to_point_in_qua(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        qubit.add_point("target", {"virtual_dot_1": 0.3}, duration=100)

        with qua.program() as prog:
            qubit.ramp_to_point("target", ramp_duration=20)

        assert prog is not None


class TestReset:
    def test_thermal_reset_in_qua(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        with qua.program() as prog:
            qubit.reset("thermal")

        assert prog is not None


class TestFluentAPI:
    def test_with_step_point_returns_self(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        result = qubit.with_step_point("load", voltages={"virtual_dot_1": 0.1}, duration=100)
        assert result is qubit

    def test_with_ramp_point_returns_self(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        result = qubit.with_ramp_point(
            "unload", voltages={"virtual_dot_1": 0.0}, duration=100, ramp_duration=16
        )
        assert result is qubit

    def test_chained_fluent_api(self, qd_machine):
        qubit = qd_machine.qubits["Q1"]
        result = (
            qubit.with_step_point("idle", voltages={"virtual_dot_1": 0.0}, duration=100)
            .with_step_point("load", voltages={"virtual_dot_1": 0.2}, duration=200)
            .with_ramp_point(
                "measure", voltages={"virtual_dot_1": 0.5}, duration=100, ramp_duration=16
            )
        )
        assert result is qubit
        assert "idle" in qubit.macros
        assert "load" in qubit.macros
        assert "measure" in qubit.macros
