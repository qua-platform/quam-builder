"""
Comprehensive tests for voltage point macro methods across all quantum dot classes.

This file tests the following methods:
- add_point: Adding voltage point macros
- step_to_point: Stepping to a predefined point
- ramp_to_point: Ramping to a predefined point
- go_to_voltages: Agnostic voltage setting (for use in simultaneous blocks)
- step_to_voltages: Stepping to specific voltages
- ramp_to_voltages: Ramping to specific voltages

Tested classes:
- BarrierGate
- QuantumDot
- QuantumDotPair
- LDQubit
- LDQubitPair
"""

import pytest
from qm import qua


# ============================================================================
# BarrierGate Tests
# ============================================================================


class TestBarrierGateVoltageMethods:
    """Tests for BarrierGate voltage methods."""

    def test_barrier_gate_go_to_voltages(self, machine):
        """Test BarrierGate.go_to_voltages method."""
        barrier = machine.barrier_gates["virtual_barrier_1"]
        seq = machine.voltage_sequences["main_qpu"]

        with qua.program() as prog:
            with seq.simultaneous(duration=100):
                barrier.go_to_voltages(0.5, duration=16)

        # Verify the method runs without error
        assert barrier is not None

    def test_barrier_gate_step_to_voltages(self, machine):
        """Test BarrierGate.step_to_voltages method."""
        barrier = machine.barrier_gates["virtual_barrier_1"]

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            barrier.step_to_voltages(0.3, duration=100)

        # Verify current_voltage is updated
        assert barrier.current_voltage == 0.3

    def test_barrier_gate_ramp_to_voltages(self, machine):
        """Test BarrierGate.ramp_to_voltages method."""
        barrier = machine.barrier_gates["virtual_barrier_2"]

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            barrier.ramp_to_voltages(0.4, ramp_duration=500, duration=16)

        # Verify current_voltage is updated
        assert barrier.current_voltage == 0.4

    def test_barrier_gate_no_voltage_sequence_error(self):
        """Test that BarrierGate raises error when voltage_sequence is None."""
        from quam_builder.architecture.quantum_dots.components import (
            BarrierGate,
            VoltageGate,
        )
        from quam.components.ports import LFFEMAnalogOutputPort
        from quam.components import StickyChannelAddon

        # Create a standalone BarrierGate without a machine
        standalone_gate = VoltageGate(
            id="standalone",
            opx_output=LFFEMAnalogOutputPort("con1", 6, port_id=1),
            sticky=StickyChannelAddon(duration=16, digital=False),
        )
        standalone_barrier = BarrierGate(
            id="standalone_barrier", physical_channel=standalone_gate
        )

        with pytest.raises(
            RuntimeError, match="QuantumDot.*has no VoltageSequence"
        ):
            with qua.program() as prog:
                standalone_barrier.step_to_voltages(0.1)


# ============================================================================
# QuantumDot Tests
# ============================================================================


class TestQuantumDotVoltageMethods:
    """Tests for QuantumDot voltage methods."""

    def test_quantum_dot_go_to_voltages(self, machine):
        """Test QuantumDot.go_to_voltages method."""
        qd = machine.quantum_dots["virtual_dot_1"]
        seq = machine.voltage_sequences["main_qpu"]

        with qua.program() as prog:
            with seq.simultaneous(duration=100):
                qd.go_to_voltages(0.2, duration=16)

        assert qd is not None

    def test_quantum_dot_step_to_voltages(self, machine):
        """Test QuantumDot.step_to_voltages method."""
        qd = machine.quantum_dots["virtual_dot_2"]

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qd.step_to_voltages(0.15, duration=100)

        assert qd is not None

    def test_quantum_dot_ramp_to_voltages(self, machine):
        """Test QuantumDot.ramp_to_voltages method."""
        qd = machine.quantum_dots["virtual_dot_3"]

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qd.ramp_to_voltages(0.25, ramp_duration=500, duration=16)

        assert qd is not None

    def test_quantum_dot_add_point(self, machine):
        """Test QuantumDot.add_point method."""
        qd = machine.quantum_dots["virtual_dot_1"]

        voltages = {
            "virtual_dot_1": 0.1,
            "virtual_barrier_1": 0.4,
            "virtual_barrier_2": 0.45,
        }
        qd.add_point(point_name="test_point", voltages=voltages, duration=100)

        # Verify point is stored internally
        assert "test_point" in qd.points
        assert qd.points["test_point"] == voltages

        # Verify point is added to gate_set
        gate_set = qd.voltage_sequence.gate_set
        expected_name = f"{qd.id}_test_point"
        assert expected_name in gate_set.macros

    def test_quantum_dot_add_point_duplicate_error(self, machine):
        """Test that adding a duplicate point raises an error."""
        qd = machine.quantum_dots["virtual_dot_2"]

        voltages = {"virtual_dot_2": 0.1}
        qd.add_point(point_name="duplicate", voltages=voltages, duration=100)

        with pytest.raises(ValueError, match="already exists"):
            qd.add_point(point_name="duplicate", voltages=voltages, duration=100)

    def test_quantum_dot_add_point_replace_existing(self, machine):
        """Test replacing an existing point."""
        qd = machine.quantum_dots["virtual_dot_3"]

        voltages_old = {"virtual_dot_3": 0.1}
        voltages_new = {"virtual_dot_3": 0.2}

        qd.add_point(point_name="replaceable", voltages=voltages_old, duration=100)
        qd.add_point(
            point_name="replaceable",
            voltages=voltages_new,
            duration=200,
            replace_existing_point=True,
        )

        assert qd.points["replaceable"] == voltages_new

    def test_quantum_dot_step_to_point(self, machine):
        """Test QuantumDot.step_to_point method."""
        qd = machine.quantum_dots["virtual_dot_1"]

        voltages = {"virtual_dot_1": 0.15, "virtual_barrier_1": 0.35}
        qd.add_point(point_name="step_point", voltages=voltages, duration=100)

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qd.step_to_point("step_point", duration=100)

        # Verify no errors

    def test_quantum_dot_step_to_point_not_found(self, machine):
        """Test that stepping to a non-existent point raises an error."""
        qd = machine.quantum_dots["virtual_dot_4"]

        with pytest.raises(ValueError, match="not in registered points"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                qd.step_to_point("nonexistent", duration=100)

    def test_quantum_dot_ramp_to_point(self, machine):
        """Test QuantumDot.ramp_to_point method."""
        qd = machine.quantum_dots["virtual_dot_2"]

        voltages = {"virtual_dot_2": 0.2, "virtual_barrier_2": 0.4}
        qd.add_point(point_name="ramp_point", voltages=voltages, duration=100)

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qd.ramp_to_point("ramp_point", ramp_duration=500, duration=16)

        # Verify no errors

    def test_quantum_dot_ramp_to_point_not_found(self, machine):
        """Test that ramping to a non-existent point raises an error."""
        qd = machine.quantum_dots["virtual_dot_1"]

        with pytest.raises(ValueError, match="not in registered points"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                qd.ramp_to_point("nonexistent", ramp_duration=500, duration=16)


# ============================================================================
# QuantumDotPair Tests
# ============================================================================


class TestQuantumDotPairVoltageMethods:
    """Tests for QuantumDotPair voltage point methods."""

    def test_quantum_dot_pair_add_point(self, machine):
        """Test QuantumDotPair.add_point method."""
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]

        voltages = {
            "virtual_dot_1": 0.1,
            "virtual_dot_2": 0.15,
            "virtual_barrier_2": 0.4,
        }
        pair.add_point(point_name="pair_point", voltages=voltages, duration=100)

        # Verify point is stored internally
        assert "pair_point" in pair.points
        assert pair.points["pair_point"] == voltages

        # Verify point is added to gate_set
        gate_set = pair.voltage_sequence.gate_set
        expected_name = f"{pair.id}_pair_point"
        assert expected_name in gate_set.macros

    def test_quantum_dot_pair_add_point_duplicate_error(self, machine):
        """Test that adding a duplicate point raises an error."""
        pair = machine.quantum_dot_pairs["dot3_dot4_pair"]

        voltages = {"virtual_dot_3": 0.2, "virtual_dot_4": 0.25}
        pair.add_point(point_name="duplicate_pair", voltages=voltages, duration=100)

        with pytest.raises(ValueError, match="already exists"):
            pair.add_point(point_name="duplicate_pair", voltages=voltages, duration=100)

    def test_quantum_dot_pair_step_to_point(self, machine):
        """Test QuantumDotPair.step_to_point method."""
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]

        voltages = {"virtual_dot_1": 0.1, "virtual_dot_2": 0.2}
        pair.add_point(point_name="step_pair_point", voltages=voltages, duration=100)

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            pair.step_to_point("step_pair_point", duration=100)

        # Verify no errors

    def test_quantum_dot_pair_step_to_point_not_found(self, machine):
        """Test that stepping to a non-existent point raises an error."""
        pair = machine.quantum_dot_pairs["dot3_dot4_pair"]

        with pytest.raises(ValueError, match="not in registered points"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                pair.step_to_point("nonexistent_pair", duration=100)

    def test_quantum_dot_pair_ramp_to_point(self, machine):
        """Test QuantumDotPair.ramp_to_point method."""
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]

        voltages = {"virtual_dot_1": 0.15, "virtual_dot_2": 0.25}
        pair.add_point(point_name="ramp_pair_point", voltages=voltages, duration=100)

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            pair.ramp_to_point("ramp_pair_point", ramp_duration=500, duration=16)

        # Verify no errors

    def test_quantum_dot_pair_ramp_to_point_not_found(self, machine):
        """Test that ramping to a non-existent point raises an error."""
        pair = machine.quantum_dot_pairs["dot3_dot4_pair"]

        with pytest.raises(ValueError, match="not in registered points"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                pair.ramp_to_point("nonexistent_pair", ramp_duration=500, duration=16)


# ============================================================================
# LDQubit Tests
# ============================================================================


class TestLDQubitVoltageMethods:
    """Tests for LDQubit voltage methods."""

    def test_ld_qubit_go_to_voltages(self, machine):
        """Test LDQubit.go_to_voltages method (delegates to quantum_dot)."""
        qubit = machine.qubits["Q1"]
        seq = machine.voltage_sequences["main_qpu"]

        with qua.program() as prog:
            with seq.simultaneous(duration=100):
                qubit.go_to_voltages(0.3, duration=16)

        assert qubit is not None

    def test_ld_qubit_step_to_voltages(self, machine):
        """Test LDQubit.step_to_voltages method (delegates to quantum_dot)."""
        qubit = machine.qubits["Q2"]

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qubit.step_to_voltages(0.25, duration=100)

        assert qubit is not None

    def test_ld_qubit_ramp_to_voltages(self, machine):
        """Test LDQubit.ramp_to_voltages method (delegates to quantum_dot)."""
        qubit = machine.qubits["Q3"]

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qubit.ramp_to_voltages(0.35, ramp_duration=500, duration=16)

        assert qubit is not None

    def test_ld_qubit_add_point_with_qubit_names(self, machine):
        """Test LDQubit.add_point with qubit names in voltages dict."""
        qubit = machine.qubits["Q1"]

        # Use qubit names which should be mapped to quantum dot names
        voltages = {
            "Q1": 0.1,  # Should be mapped to virtual_dot_1
            "virtual_barrier_1": 0.4,
            "virtual_barrier_2": 0.45,
        }
        qubit.add_point(point_name="qubit_point", voltages=voltages, duration=100)

        # Verify point is stored with original names
        assert "qubit_point" in qubit.points
        assert qubit.points["qubit_point"] == voltages

        # Verify point is added to gate_set with mapped names
        gate_set = qubit.voltage_sequence.gate_set
        expected_name = f"{qubit.name}_qubit_point"
        assert expected_name in gate_set.macros

    def test_ld_qubit_add_point_duplicate_error(self, machine):
        """Test that adding a duplicate point raises an error."""
        qubit = machine.qubits["Q2"]

        voltages = {"Q2": 0.1}
        qubit.add_point(point_name="duplicate_qubit", voltages=voltages, duration=100)

        with pytest.raises(ValueError, match="already exists"):
            qubit.add_point(
                point_name="duplicate_qubit", voltages=voltages, duration=100
            )

    def test_ld_qubit_step_to_point(self, machine):
        """Test LDQubit.step_to_point method."""
        qubit = machine.qubits["Q1"]

        voltages = {"Q1": 0.15, "virtual_barrier_1": 0.35}
        qubit.add_point(point_name="qubit_step_point", voltages=voltages, duration=100)

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qubit.step_to_point("qubit_step_point", duration=100)

        # Verify no errors

    def test_ld_qubit_step_to_point_not_found(self, machine):
        """Test that stepping to a non-existent point raises an error."""
        qubit = machine.qubits["Q4"]

        with pytest.raises(ValueError, match="not in registered points"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                qubit.step_to_point("nonexistent_qubit", duration=100)

    def test_ld_qubit_ramp_to_point(self, machine):
        """Test LDQubit.ramp_to_point method."""
        qubit = machine.qubits["Q2"]

        voltages = {"Q2": 0.2, "virtual_barrier_2": 0.4}
        qubit.add_point(point_name="qubit_ramp_point", voltages=voltages, duration=100)

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qubit.ramp_to_point("qubit_ramp_point", ramp_duration=500, duration=16)

        # Verify no errors

    def test_ld_qubit_ramp_to_point_not_found(self, machine):
        """Test that ramping to a non-existent point raises an error."""
        qubit = machine.qubits["Q1"]

        with pytest.raises(ValueError, match="not in registered points"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                qubit.ramp_to_point("nonexistent_qubit", ramp_duration=500, duration=16)


# ============================================================================
# LDQubitPair Tests
# ============================================================================


class TestLDQubitPairVoltageMethods:
    """Tests for LDQubitPair voltage point methods."""

    def test_ld_qubit_pair_add_point_with_qubit_names(self, machine):
        """Test LDQubitPair.add_point with qubit names in voltages dict."""
        qubit_pair = machine.qubit_pairs["Q1_Q2"]

        # Use qubit names which should be mapped to quantum dot names
        voltages = {
            "Q1": 0.1,  # Should be mapped to virtual_dot_1
            "Q2": 0.15,  # Should be mapped to virtual_dot_2
            "virtual_barrier_2": 0.4,
        }
        qubit_pair.add_point(
            point_name="qubit_pair_point", voltages=voltages, duration=100
        )

        # Verify point is stored with original names
        assert "qubit_pair_point" in qubit_pair.points
        assert qubit_pair.points["qubit_pair_point"] == voltages

        # Verify point is added to gate_set
        gate_set = qubit_pair.voltage_sequence.gate_set
        expected_name = f"{qubit_pair.id}_qubit_pair_point"
        assert expected_name in gate_set.macros

    def test_ld_qubit_pair_add_point_duplicate_error(self, machine):
        """Test that adding a duplicate point raises an error."""
        qubit_pair = machine.qubit_pairs["Q3_Q4"]

        voltages = {"Q3": 0.2, "Q4": 0.25}
        qubit_pair.add_point(
            point_name="duplicate_qubit_pair", voltages=voltages, duration=100
        )

        with pytest.raises(ValueError, match="already exists"):
            qubit_pair.add_point(
                point_name="duplicate_qubit_pair", voltages=voltages, duration=100
            )

    def test_ld_qubit_pair_step_to_point(self, machine):
        """Test LDQubitPair.step_to_point method."""
        qubit_pair = machine.qubit_pairs["Q1_Q2"]

        voltages = {"Q1": 0.1, "Q2": 0.2}
        qubit_pair.add_point(
            point_name="step_qubit_pair_point", voltages=voltages, duration=100
        )

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qubit_pair.step_to_point("step_qubit_pair_point", duration=100)

        # Verify no errors

    def test_ld_qubit_pair_step_to_point_not_found(self, machine):
        """Test that stepping to a non-existent point raises an error."""
        qubit_pair = machine.qubit_pairs["Q3_Q4"]

        with pytest.raises(ValueError, match="not in registered points"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                qubit_pair.step_to_point("nonexistent_qubit_pair", duration=100)

    def test_ld_qubit_pair_ramp_to_point(self, machine):
        """Test LDQubitPair.ramp_to_point method."""
        qubit_pair = machine.qubit_pairs["Q1_Q2"]

        voltages = {"Q1": 0.15, "Q2": 0.25}
        qubit_pair.add_point(
            point_name="ramp_qubit_pair_point", voltages=voltages, duration=100
        )

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qubit_pair.ramp_to_point(
                "ramp_qubit_pair_point", ramp_duration=500, duration=16
            )

        # Verify no errors

    def test_ld_qubit_pair_ramp_to_point_not_found(self, machine):
        """Test that ramping to a non-existent point raises an error."""
        qubit_pair = machine.qubit_pairs["Q3_Q4"]

        with pytest.raises(ValueError, match="not in registered points"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                qubit_pair.ramp_to_point(
                    "nonexistent_qubit_pair", ramp_duration=500, duration=16
                )


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegrationVoltagePointMethods:
    """Integration tests for voltage point methods across multiple classes."""

    def test_multiple_components_simultaneous_step_to_point(self, machine):
        """Test simultaneous stepping to points across multiple components."""
        q1 = machine.qubits["Q1"]
        q2 = machine.qubits["Q2"]
        pair = machine.qubit_pairs["Q3_Q4"]

        # Add points for each component
        q1.add_point(
            "init", {"Q1": 0.1, "virtual_barrier_1": 0.4, "virtual_barrier_2": 0.45}
        )
        q2.add_point(
            "init", {"Q2": 0.15, "virtual_barrier_1": 0.4, "virtual_barrier_2": 0.45}
        )
        pair.add_point(
            "two_qubit_gate",
            {"Q3": 0.2, "Q4": 0.25, "virtual_barrier_3": 0.42},
        )

        # Execute simultaneous stepping
        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            with seq.simultaneous(duration=1000):
                q1.step_to_point("init")
                q2.step_to_point("init")
                pair.step_to_point("two_qubit_gate")

        # Verify no errors

    def test_mixed_voltage_operations(self, machine):
        """Test mixing voltage operations (direct voltage and points)."""
        qd1 = machine.quantum_dots["virtual_dot_1"]
        qd2 = machine.quantum_dots["virtual_dot_2"]
        barrier = machine.barrier_gates["virtual_barrier_1"]

        # Add a point for qd1
        qd1.add_point("load", {"virtual_dot_1": 0.5})

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            # Mix point stepping with direct voltage commands
            qd1.step_to_point("load", duration=100)
            qd2.step_to_voltages(0.3, duration=100)
            barrier.ramp_to_voltages(0.4, ramp_duration=500, duration=16)

        # Verify no errors

    def test_sequential_then_simultaneous_operations(self, machine):
        """Test sequential operations followed by simultaneous operations."""
        q1 = machine.qubits["Q1"]
        q2 = machine.qubits["Q2"]
        q3 = machine.qubits["Q3"]

        q1.add_point("idle", {"Q1": 0.1})
        q2.add_point("idle", {"Q2": 0.15})
        q3.add_point("idle", {"Q3": 0.2})

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]

            # Sequential operations
            q1.step_to_voltages(0.5, duration=1000)
            q2.step_to_voltages(0.1, duration=1000)

            # Then simultaneous operations
            with seq.simultaneous(duration=1000):
                q1.step_to_point("idle")
                q2.step_to_point("idle")
                q3.step_to_point("idle")

        # Verify no errors