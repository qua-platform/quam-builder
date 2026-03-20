"""Tests for QuantumDot.

All objects are real — no mocks or stubs.
"""

from qm import qua

from quam_builder.architecture.quantum_dots.components import QuantumDot
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros


class TestQuantumDotProperties:
    def test_quantum_dots_exist(self, qd_machine):
        assert len(qd_machine.quantum_dots) == 4

    def test_quantum_dot_type(self, qd_machine):
        for qd in qd_machine.quantum_dots.values():
            assert isinstance(qd, QuantumDot)

    def test_has_physical_channel(self, qd_machine):
        for qd in qd_machine.quantum_dots.values():
            assert qd.physical_channel is not None

    def test_name_property(self, qd_machine):
        for qd in qd_machine.quantum_dots.values():
            assert isinstance(qd.name, str)
            assert len(qd.name) > 0

    def test_machine_reference(self, qd_machine):
        qd = list(qd_machine.quantum_dots.values())[0]
        assert qd.machine is qd_machine

    def test_voltage_sequence_accessible(self, qd_machine):
        qd = list(qd_machine.quantum_dots.values())[0]
        assert qd.voltage_sequence is not None

    def test_current_voltage_default(self, qd_machine):
        for qd in qd_machine.quantum_dots.values():
            assert qd.current_voltage == 0.0

    def test_charge_number_default(self, qd_machine):
        for qd in qd_machine.quantum_dots.values():
            assert qd.charge_number == 0


class TestQuantumDotVoltageOps:
    def test_update_current_voltage(self, qd_machine):
        qd = list(qd_machine.quantum_dots.values())[0]
        qd._update_current_voltage(0.42)
        assert qd.current_voltage == 0.42

    def test_add_point(self, qd_machine):
        qd = list(qd_machine.quantum_dots.values())[0]
        full_name = qd.add_point("idle", {qd.id: 0.1}, duration=100)
        macros = qd.voltage_sequence.gate_set.get_macros()
        assert full_name in macros

    def test_step_to_point_in_qua(self, qd_machine):
        qd = list(qd_machine.quantum_dots.values())[0]
        qd.add_point("test_pt", {qd.id: 0.2}, duration=100)
        with qua.program() as prog:
            qd.step_to_point("test_pt")
        assert prog is not None

    def test_go_to_voltages_in_qua(self, qd_machine):
        qd = list(qd_machine.quantum_dots.values())[0]
        with qua.program() as prog:
            qd.go_to_voltages({qd.id: 0.15}, duration=100)
        assert prog is not None


class TestQuantumDotPlay:
    def test_play_in_qua(self, qd_machine):
        qd = list(qd_machine.quantum_dots.values())[0]
        with qua.program() as prog:
            qd.play("half_max_square")
        assert prog is not None


class TestQuantumDotCatalog:
    """Verify QuantumDot receives state macros after wire_machine_macros()."""

    def test_has_initialize_macro(self, qd_machine, reset_catalog):
        wire_machine_macros(qd_machine)
        for qd in qd_machine.quantum_dots.values():
            assert "initialize" in qd.macros, f"{qd.id} missing 'initialize' macro"

    def test_no_generic_measure_macro_on_quantum_dot(self, qd_machine, reset_catalog):
        """QuantumDot should not have a generic measure macro; measurement is component-specific."""
        wire_machine_macros(qd_machine)
        for qd in qd_machine.quantum_dots.values():
            assert "measure" not in qd.macros, f"{qd.id} should not have generic 'measure' macro"

    def test_has_empty_macro(self, qd_machine, reset_catalog):
        wire_machine_macros(qd_machine)
        for qd in qd_machine.quantum_dots.values():
            assert "empty" in qd.macros, f"{qd.id} missing 'empty' macro"
