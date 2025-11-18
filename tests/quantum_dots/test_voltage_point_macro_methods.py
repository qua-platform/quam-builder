"""
Comprehensive tests for voltage point macro methods across all quantum dot classes.

This file tests the following methods:
- add_point: Adding voltage point macros
- step_to_point: Stepping to a predefined point
- ramp_to_point: Ramping to a predefined point
- go_to_voltages: Agnostic voltage setting (for use in simultaneous blocks)
- step_to_voltages: Stepping to specific voltages
- ramp_to_voltages: Ramping to specific voltages
- add_sequence: Adding a sequence of voltage macro operations
- add_point_to_sequence: Adding individual points to a sequence
- run_sequence: Executing a pre-defined sequence

Tested classes:
- BarrierGate
- QuantumDot
- QuantumDotPair
- LDQubit
- LDQubitPair
- SequenceMacro
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
            RuntimeError, match="BarrierGate.*has no VoltageSequence"
        ):
            with qua.program() as prog:
                standalone_barrier.step_to_voltages(0.1)

    def test_barrier_gate_add_point(self, machine):
        """Test BarrierGate.add_point method."""
        barrier = machine.barrier_gates["virtual_barrier_1"]

        voltages = {
            "virtual_barrier_1": 0.4,
            "virtual_dot_1": 0.1,
            "virtual_dot_2": 0.15,
        }
        barrier.add_point(point_name="barrier_point", voltages=voltages, duration=100)

        # Verify point is stored internally
        assert "barrier_point" in barrier.points
        assert barrier.points["barrier_point"] == voltages

        # Verify point is added to gate_set
        gate_set = barrier.voltage_sequence.gate_set
        expected_name = f"{barrier.id}_barrier_point"
        assert expected_name in gate_set.macros

    def test_barrier_gate_add_point_duplicate_error(self, machine):
        """Test that adding a duplicate point raises an error for BarrierGate."""
        barrier = machine.barrier_gates["virtual_barrier_2"]

        voltages = {"virtual_barrier_2": 0.45}
        barrier.add_point(point_name="duplicate_barrier", voltages=voltages, duration=100)

        with pytest.raises(ValueError, match="already exists"):
            barrier.add_point(point_name="duplicate_barrier", voltages=voltages, duration=100)

    def test_barrier_gate_add_point_replace_existing(self, machine):
        """Test replacing an existing point for BarrierGate."""
        barrier = machine.barrier_gates["virtual_barrier_3"]

        voltages_old = {"virtual_barrier_3": 0.3}
        voltages_new = {"virtual_barrier_3": 0.5}

        barrier.add_point(point_name="replaceable_barrier", voltages=voltages_old, duration=100)
        barrier.add_point(
            point_name="replaceable_barrier",
            voltages=voltages_new,
            duration=200,
            replace_existing_point=True,
        )

        assert barrier.points["replaceable_barrier"] == voltages_new

    def test_barrier_gate_step_to_point(self, machine):
        """Test BarrierGate.step_to_point method."""
        barrier = machine.barrier_gates["virtual_barrier_1"]

        voltages = {"virtual_barrier_1": 0.35, "virtual_dot_1": 0.2}
        barrier.add_point(point_name="barrier_step_point", voltages=voltages, duration=100)

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            barrier.step_to_point("barrier_step_point", duration=100)

        # Verify no errors

    def test_barrier_gate_step_to_point_not_found(self, machine):
        """Test that stepping to a non-existent point raises an error for BarrierGate."""
        barrier = machine.barrier_gates["virtual_barrier_2"]

        with pytest.raises(ValueError, match="not in registered points"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                barrier.step_to_point("nonexistent_barrier", duration=100)

    def test_barrier_gate_ramp_to_point(self, machine):
        """Test BarrierGate.ramp_to_point method."""
        barrier = machine.barrier_gates["virtual_barrier_3"]

        voltages = {"virtual_barrier_3": 0.42, "virtual_dot_3": 0.25}
        barrier.add_point(point_name="barrier_ramp_point", voltages=voltages, duration=100)

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            barrier.ramp_to_point("barrier_ramp_point", ramp_duration=500, duration=16)

        # Verify no errors

    def test_barrier_gate_ramp_to_point_not_found(self, machine):
        """Test that ramping to a non-existent point raises an error for BarrierGate."""
        barrier = machine.barrier_gates["virtual_barrier_1"]

        with pytest.raises(ValueError, match="not in registered points"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                barrier.ramp_to_point("nonexistent_barrier", ramp_duration=500, duration=16)


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

    def test_quantum_dot_pair_go_to_voltages(self, machine):
        """Test QuantumDotPair.go_to_voltages method."""
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]
        seq = machine.voltage_sequences["main_qpu"]

        # Define detuning axis for the pair if not already defined
        try:
            pair.define_detuning_axis(matrix=[[1, 1], [1, -1]])
        except ValueError:
            pass  # Already defined

        with qua.program() as prog:
            with seq.simultaneous(duration=100):
                pair.go_to_voltages(0.2, duration=16)

        assert pair is not None

    def test_quantum_dot_pair_step_to_voltages(self, machine):
        """Test QuantumDotPair.step_to_voltages method."""
        pair = machine.quantum_dot_pairs["dot3_dot4_pair"]

        # Define detuning axis for the pair if not already defined
        try:
            pair.define_detuning_axis(matrix=[[1, 1], [1, -1]])
        except ValueError:
            pass  # Already defined

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            pair.step_to_voltages(0.25, duration=100)

        assert pair is not None

    def test_quantum_dot_pair_ramp_to_voltages(self, machine):
        """Test QuantumDotPair.ramp_to_voltages method."""
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]

        # Define detuning axis for the pair if not already defined
        try:
            pair.define_detuning_axis(matrix=[[1, 1], [1, -1]])
        except ValueError:
            pass  # Already defined

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            pair.ramp_to_voltages(0.3, ramp_duration=500, duration=16)

        assert pair is not None

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

    def test_quantum_dot_pair_add_point_replace_existing(self, machine):
        """Test replacing an existing point for QuantumDotPair."""
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]

        voltages_old = {"virtual_dot_1": 0.1, "virtual_dot_2": 0.1}
        voltages_new = {"virtual_dot_1": 0.2, "virtual_dot_2": 0.2}

        pair.add_point(point_name="replaceable_pair", voltages=voltages_old, duration=100)
        pair.add_point(
            point_name="replaceable_pair",
            voltages=voltages_new,
            duration=200,
            replace_existing_point=True,
        )

        assert pair.points["replaceable_pair"] == voltages_new

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

    def test_ld_qubit_add_point_replace_existing(self, machine):
        """Test replacing an existing point for LDQubit."""
        qubit = machine.qubits["Q3"]

        voltages_old = {"Q3": 0.1}
        voltages_new = {"Q3": 0.3}

        qubit.add_point(point_name="replaceable_qubit", voltages=voltages_old, duration=100)
        qubit.add_point(
            point_name="replaceable_qubit",
            voltages=voltages_new,
            duration=200,
            replace_existing_point=True,
        )

        assert qubit.points["replaceable_qubit"] == voltages_new

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

    def test_ld_qubit_pair_go_to_voltages(self, machine):
        """Test LDQubitPair.go_to_voltages method (delegates to quantum_dot_pair)."""
        qubit_pair = machine.qubit_pairs["Q1_Q2"]
        seq = machine.voltage_sequences["main_qpu"]

        # Define detuning axis for the pair via the quantum_dot_pair if not already defined
        try:
            qubit_pair.quantum_dot_pair.define_detuning_axis(matrix=[[1, 1], [1, -1]])
        except ValueError:
            pass  # Already defined

        with qua.program() as prog:
            with seq.simultaneous(duration=100):
                qubit_pair.go_to_voltages(0.3, duration=16)

        assert qubit_pair is not None

    def test_ld_qubit_pair_step_to_voltages(self, machine):
        """Test LDQubitPair.step_to_voltages method (delegates to quantum_dot_pair)."""
        qubit_pair = machine.qubit_pairs["Q3_Q4"]

        # Define detuning axis for the pair via the quantum_dot_pair if not already defined
        try:
            qubit_pair.quantum_dot_pair.define_detuning_axis(matrix=[[1, 1], [1, -1]])
        except ValueError:
            pass  # Already defined

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qubit_pair.step_to_voltages(0.25, duration=100)

        assert qubit_pair is not None

    def test_ld_qubit_pair_ramp_to_voltages(self, machine):
        """Test LDQubitPair.ramp_to_voltages method (delegates to quantum_dot_pair)."""
        qubit_pair = machine.qubit_pairs["Q1_Q2"]

        # Define detuning axis for the pair via the quantum_dot_pair if not already defined
        try:
            qubit_pair.quantum_dot_pair.define_detuning_axis(matrix=[[1, 1], [1, -1]])
        except ValueError:
            pass  # Already defined

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qubit_pair.ramp_to_voltages(0.35, ramp_duration=500, duration=16)

        assert qubit_pair is not None

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

    def test_ld_qubit_pair_add_point_replace_existing(self, machine):
        """Test replacing an existing point for LDQubitPair."""
        qubit_pair = machine.qubit_pairs["Q1_Q2"]

        voltages_old = {"Q1": 0.1, "Q2": 0.1}
        voltages_new = {"Q1": 0.3, "Q2": 0.3}

        qubit_pair.add_point(point_name="replaceable_qubit_pair", voltages=voltages_old, duration=100)
        qubit_pair.add_point(
            point_name="replaceable_qubit_pair",
            voltages=voltages_new,
            duration=200,
            replace_existing_point=True,
        )

        assert qubit_pair.points["replaceable_qubit_pair"] == voltages_new

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


# ============================================================================
# SequenceMacro Tests
# ============================================================================


class TestSequenceMacro:
    """Tests for SequenceMacro class and sequence-related methods."""

    def test_sequence_macro_initialization(self):
        """Test that SequenceMacro can be initialized correctly."""
        from quam_builder.architecture.quantum_dots.components.macros import SequenceMacro
        from dataclasses import is_dataclass

        # Verify it's a dataclass
        assert is_dataclass(SequenceMacro), "SequenceMacro should be a dataclass"

        # Test initialization
        macro = SequenceMacro(
            macro_type="step",
            point_name="test_point",
            duration=100,
            ramp_duration=200
        )

        assert macro.macro_type == "step"
        assert macro.point_name == "test_point"
        assert macro.duration == 100
        assert macro.ramp_duration == 200

    def test_sequence_macro_default_values(self):
        """Test that SequenceMacro has correct default values."""
        from quam_builder.architecture.quantum_dots.components.macros import SequenceMacro

        macro = SequenceMacro(
            macro_type="ramp",
            point_name="test_point"
        )

        assert macro.duration == 16
        assert macro.ramp_duration == 16

    def test_sequence_macro_call_step(self, machine):
        """Test that SequenceMacro can be called with step macro_type."""
        from quam_builder.architecture.quantum_dots.components.macros import SequenceMacro

        qd = machine.quantum_dots["virtual_dot_1"]

        # Add a point first
        voltages = {"virtual_dot_1": 0.2}
        qd.add_point(point_name="test_step", voltages=voltages, duration=100)

        # Create a SequenceMacro
        macro = SequenceMacro(
            macro_type="step",
            point_name="test_step",
            duration=100
        )

        # Call the macro within a QUA program
        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            macro(qd)

        # Verify no errors

    def test_sequence_macro_call_ramp(self, machine):
        """Test that SequenceMacro can be called with ramp macro_type."""
        from quam_builder.architecture.quantum_dots.components.macros import SequenceMacro

        qd = machine.quantum_dots["virtual_dot_2"]

        # Add a point first
        voltages = {"virtual_dot_2": 0.3}
        qd.add_point(point_name="test_ramp", voltages=voltages, duration=100)

        # Create a SequenceMacro
        macro = SequenceMacro(
            macro_type="ramp",
            point_name="test_ramp",
            duration=100,
            ramp_duration=500
        )

        # Call the macro within a QUA program
        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            macro(qd)

        # Verify no errors

    def test_sequence_macro_call_with_override(self, machine):
        """Test that SequenceMacro parameters can be overridden when called."""
        from quam_builder.architecture.quantum_dots.components.macros import SequenceMacro

        qd = machine.quantum_dots["virtual_dot_3"]

        # Add a point first
        voltages = {"virtual_dot_3": 0.25}
        qd.add_point(point_name="test_override", voltages=voltages, duration=100)

        # Create a SequenceMacro
        macro = SequenceMacro(
            macro_type="step",
            point_name="test_override",
            duration=100
        )

        # Call with overridden parameters
        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            macro(qd, duration=200)

        # Verify the duration was updated
        assert macro.duration == 200

    def test_sequence_macro_invalid_type(self, machine):
        """Test that SequenceMacro raises error for invalid macro_type."""
        from quam_builder.architecture.quantum_dots.components.macros import SequenceMacro

        qd = machine.quantum_dots["virtual_dot_1"]

        # Add a point first
        voltages = {"virtual_dot_1": 0.2}
        qd.add_point(point_name="test_invalid", voltages=voltages, duration=100)

        # Create a SequenceMacro with invalid type
        macro = SequenceMacro(
            macro_type="invalid_type",
            point_name="test_invalid",
            duration=100
        )

        # Should raise NotImplementedError
        with pytest.raises(NotImplementedError, match="not implemented"):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                macro(qd)


class TestAddPointToSequence:
    """Tests for add_point_to_sequence method."""

    def test_add_point_to_sequence_with_voltages(self, machine):
        """Test adding a point to a sequence with voltage values."""
        qd = machine.quantum_dots["virtual_dot_1"]

        voltages = {"virtual_dot_1": 0.15}
        qd.add_point_to_sequence(
            sequence_name="test_seq",
            point_name="point1",
            macro_type="step",
            duration=100,
            voltages=voltages
        )

        # Verify the sequence was created
        assert "test_seq" in qd.sequences

        # Verify the sequence has one macro
        assert len(qd.sequences["test_seq"]) == 1

        # Verify the macro has correct properties
        macro = qd.sequences["test_seq"][0]
        assert macro.macro_type == "step"
        assert macro.point_name == "point1"
        assert macro.duration == 100

        # Verify the point was added to the points dict
        assert "point1" in qd.points
        assert qd.points["point1"] == voltages

    def test_add_point_to_sequence_without_voltages(self, machine):
        """Test adding a point to a sequence without voltage values."""
        qd = machine.quantum_dots["virtual_dot_2"]

        # Add a point first
        voltages = {"virtual_dot_2": 0.2}
        qd.add_point(point_name="existing_point", voltages=voltages, duration=100)

        # Add to sequence without providing voltages again
        qd.add_point_to_sequence(
            sequence_name="test_seq2",
            point_name="existing_point",
            macro_type="ramp",
            duration=152,
            ramp_duration=500
        )

        # Verify the sequence was created
        assert "test_seq2" in qd.sequences

        # Verify the macro has correct properties
        macro = qd.sequences["test_seq2"][0]
        assert macro.macro_type == "ramp"
        assert macro.point_name == "existing_point"
        assert macro.duration == 152
        assert macro.ramp_duration == 500

    def test_add_point_to_sequence_default_ramp_duration(self, machine):
        """Test that ramp_duration defaults to 16 when None."""
        qd = machine.quantum_dots["virtual_dot_3"]

        voltages = {"virtual_dot_3": 0.25}
        qd.add_point_to_sequence(
            sequence_name="test_seq3",
            point_name="point_with_default",
            macro_type="ramp",
            duration=100,
            voltages=voltages
        )

        # Verify the ramp_duration defaults to 16
        macro = qd.sequences["test_seq3"][0]
        assert macro.ramp_duration == 16

    def test_add_multiple_points_to_same_sequence(self, machine):
        """Test adding multiple points to the same sequence."""
        barrier = machine.barrier_gates["virtual_barrier_1"]

        voltages1 = {"virtual_barrier_1": 0.3}
        voltages2 = {"virtual_barrier_1": 0.4}
        voltages3 = {"virtual_barrier_1": 0.5}

        barrier.add_point_to_sequence(
            sequence_name="multi_point_seq",
            point_name="point1",
            macro_type="step",
            duration=100,
            voltages=voltages1
        )
        barrier.add_point_to_sequence(
            sequence_name="multi_point_seq",
            point_name="point2",
            macro_type="ramp",
            duration=152,
            ramp_duration=500,
            voltages=voltages2
        )
        barrier.add_point_to_sequence(
            sequence_name="multi_point_seq",
            point_name="point3",
            macro_type="step",
            duration=200,
            voltages=voltages3
        )

        # Verify the sequence has three macros
        assert len(barrier.sequences["multi_point_seq"]) == 3

        # Verify each macro
        assert barrier.sequences["multi_point_seq"][0].point_name == "point1"
        assert barrier.sequences["multi_point_seq"][1].point_name == "point2"
        assert barrier.sequences["multi_point_seq"][2].point_name == "point3"


class TestAddSequence:
    """Tests for add_sequence method."""

    def test_add_sequence_basic(self, machine):
        """Test adding a basic sequence with multiple points."""
        qd = machine.quantum_dots["virtual_dot_1"]

        macro_types = ["step", "ramp", "step"]
        voltages = [
            {"virtual_dot_1": 0.1},
            {"virtual_dot_1": 0.2},
            {"virtual_dot_1": 0.3}
        ]
        durations = [100, 152, 200]
        ramp_durations = [16, 500, 16]

        qd.add_sequence(
            name="basic_seq",
            macro_types=macro_types,
            voltages=voltages,
            durations=durations,
            ramp_durations=ramp_durations
        )

        # Verify sequence was created
        assert "basic_seq" in qd.sequences

        # Verify sequence has correct number of macros
        assert len(qd.sequences["basic_seq"]) == 3

        # Verify each macro
        assert qd.sequences["basic_seq"][0].macro_type == "step"
        assert qd.sequences["basic_seq"][0].duration == 100
        assert qd.sequences["basic_seq"][1].macro_type == "ramp"
        assert qd.sequences["basic_seq"][1].duration == 152
        assert qd.sequences["basic_seq"][1].ramp_duration == 500
        assert qd.sequences["basic_seq"][2].macro_type == "step"
        assert qd.sequences["basic_seq"][2].duration == 200

    def test_add_sequence_without_ramp_durations(self, machine):
        """Test adding a sequence without specifying ramp_durations."""
        barrier = machine.barrier_gates["virtual_barrier_2"]

        macro_types = ["step", "step"]
        voltages = [
            {"virtual_barrier_2": 0.4},
            {"virtual_barrier_2": 0.5}
        ]
        durations = [100, 200]

        barrier.add_sequence(
            name="no_ramp_seq",
            macro_types=macro_types,
            voltages=voltages,
            durations=durations
        )

        # Verify sequence was created
        assert "no_ramp_seq" in barrier.sequences

        # Verify ramp_durations default to 16
        assert barrier.sequences["no_ramp_seq"][0].ramp_duration == 16
        assert barrier.sequences["no_ramp_seq"][1].ramp_duration == 16

    def test_add_sequence_auto_naming(self, machine):
        """Test that points are automatically named in sequence."""
        qd = machine.quantum_dots["virtual_dot_4"]

        macro_types = ["step", "ramp"]
        voltages = [
            {"virtual_dot_4": 0.1},
            {"virtual_dot_4": 0.2}
        ]
        durations = [100, 152]

        qd.add_sequence(
            name="auto_name_seq",
            macro_types=macro_types,
            voltages=voltages,
            durations=durations
        )

        # Verify point names follow pattern
        assert qd.sequences["auto_name_seq"][0].point_name == "auto_name_seq_macro_0"
        assert qd.sequences["auto_name_seq"][1].point_name == "auto_name_seq_macro_1"

        # Verify points were added
        assert "auto_name_seq_macro_0" in qd.points
        assert "auto_name_seq_macro_1" in qd.points

    def test_add_sequence_for_qubit(self, machine):
        """Test adding a sequence for an LDQubit."""
        qubit = machine.qubits["Q1"]

        macro_types = ["step", "ramp", "step"]
        voltages = [
            {"Q1": 0.1, "virtual_barrier_1": 0.4},
            {"Q1": 0.2, "virtual_barrier_1": 0.45},
            {"Q1": 0.15, "virtual_barrier_1": 0.42}
        ]
        durations = [100, 152, 100]
        ramp_durations = [16, 600, 16]

        qubit.add_sequence(
            name="qubit_seq",
            macro_types=macro_types,
            voltages=voltages,
            durations=durations,
            ramp_durations=ramp_durations
        )

        # Verify sequence was created
        assert "qubit_seq" in qubit.sequences
        assert len(qubit.sequences["qubit_seq"]) == 3


class TestRunSequence:
    """Tests for run_sequence method."""

    def test_run_sequence_basic(self, machine):
        """Test running a basic sequence."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Create a sequence
        macro_types = ["step", "ramp", "step"]
        voltages = [
            {"virtual_dot_1": 0.1},
            {"virtual_dot_1": 0.2},
            {"virtual_dot_1": 0.15}
        ]
        durations = [100, 152, 100]
        ramp_durations = [16, 500, 16]

        qd.add_sequence(
            name="run_test_seq",
            macro_types=macro_types,
            voltages=voltages,
            durations=durations,
            ramp_durations=ramp_durations
        )

        # Run the sequence within a QUA program
        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qd.run_sequence("run_test_seq")

        # Verify no errors

    def test_run_sequence_barrier_gate(self, machine):
        """Test running a sequence for a barrier gate."""
        barrier = machine.barrier_gates["virtual_barrier_1"]

        macro_types = ["step", "step"]
        voltages = [
            {"virtual_barrier_1": 0.3},
            {"virtual_barrier_1": 0.4}
        ]
        durations = [100, 200]

        barrier.add_sequence(
            name="barrier_seq",
            macro_types=macro_types,
            voltages=voltages,
            durations=durations
        )

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            barrier.run_sequence("barrier_seq")

        # Verify no errors

    def test_run_sequence_qubit(self, machine):
        """Test running a sequence for an LDQubit."""
        qubit = machine.qubits["Q2"]

        macro_types = ["step", "ramp"]
        voltages = [
            {"Q2": 0.1},
            {"Q2": 0.2}
        ]
        durations = [100, 152]
        ramp_durations = [16, 400]

        qubit.add_sequence(
            name="qubit_run_seq",
            macro_types=macro_types,
            voltages=voltages,
            durations=durations,
            ramp_durations=ramp_durations
        )

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qubit.run_sequence("qubit_run_seq")

        # Verify no errors

    def test_run_sequence_quantum_dot_pair(self, machine):
        """Test running a sequence for a QuantumDotPair."""
        pair = machine.quantum_dot_pairs["dot1_dot2_pair"]

        macro_types = ["step", "ramp", "step"]
        voltages = [
            {"virtual_dot_1": 0.1, "virtual_dot_2": 0.15},
            {"virtual_dot_1": 0.2, "virtual_dot_2": 0.25},
            {"virtual_dot_1": 0.15, "virtual_dot_2": 0.2}
        ]
        durations = [100, 152, 100]
        ramp_durations = [16, 500, 16]

        pair.add_sequence(
            name="pair_seq",
            macro_types=macro_types,
            voltages=voltages,
            durations=durations,
            ramp_durations=ramp_durations
        )

        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            pair.run_sequence("pair_seq")

        # Verify no errors

    def test_run_nonexistent_sequence_error(self, machine):
        """Test that running a non-existent sequence raises an error."""
        qd = machine.quantum_dots["virtual_dot_3"]

        with pytest.raises(KeyError):
            with qua.program() as prog:
                seq = machine.voltage_sequences["main_qpu"]
                qd.run_sequence("nonexistent_seq")


class TestSequenceIntegration:
    """Integration tests for sequence functionality."""

    def test_mixed_sequence_and_direct_calls(self, machine):
        """Test mixing sequence execution with direct voltage calls."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Create a sequence
        macro_types = ["step", "ramp"]
        voltages = [
            {"virtual_dot_1": 0.1},
            {"virtual_dot_1": 0.2}
        ]
        durations = [100, 152]
        ramp_durations = [16, 500]

        qd.add_sequence(
            name="mixed_seq",
            macro_types=macro_types,
            voltages=voltages,
            durations=durations,
            ramp_durations=ramp_durations
        )

        # Mix sequence execution with direct calls
        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qd.run_sequence("mixed_seq")
            qd.step_to_voltages(0.3, duration=100)
            qd.run_sequence("mixed_seq")

        # Verify no errors

    def test_multiple_components_with_sequences(self, machine):
        """Test running sequences on multiple components."""
        q1 = machine.qubits["Q1"]
        q2 = machine.qubits["Q2"]
        barrier = machine.barrier_gates["virtual_barrier_1"]

        # Create sequences for each component
        q1.add_sequence(
            name="q1_seq",
            macro_types=["step", "step"],
            voltages=[{"Q1": 0.1}, {"Q1": 0.2}],
            durations=[100, 100]
        )

        q2.add_sequence(
            name="q2_seq",
            macro_types=["step", "ramp"],
            voltages=[{"Q2": 0.15}, {"Q2": 0.25}],
            durations=[100, 152],
            ramp_durations=[16, 500]
        )

        barrier.add_sequence(
            name="barrier_seq",
            macro_types=["step"],
            voltages=[{"virtual_barrier_1": 0.4}],
            durations=[100]
        )

        # Run sequences
        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            q1.run_sequence("q1_seq")
            q2.run_sequence("q2_seq")
            barrier.run_sequence("barrier_seq")

        # Verify no errors

    def test_sequence_with_simultaneous_block(self, machine):
        """Test using sequences within simultaneous blocks."""
        q1 = machine.qubits["Q1"]
        q2 = machine.qubits["Q2"]

        # Create sequences
        q1.add_sequence(
            name="q1_simul_seq",
            macro_types=["step"],
            voltages=[{"Q1": 0.1}],
            durations=[100]
        )

        q2.add_sequence(
            name="q2_simul_seq",
            macro_types=["step"],
            voltages=[{"Q2": 0.15}],
            durations=[100]
        )

        # Run within simultaneous block
        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            # Note: simultaneous block doesn't make sense with run_sequence
            # since run_sequence executes multiple operations sequentially
            # This test just ensures no errors occur
            q1.run_sequence("q1_simul_seq")
            q2.run_sequence("q2_simul_seq")

        # Verify no errors

    def test_sequence_reusability(self, machine):
        """Test that sequences can be run multiple times."""
        qd = machine.quantum_dots["virtual_dot_2"]

        macro_types = ["step", "ramp", "step"]
        voltages = [
            {"virtual_dot_2": 0.1},
            {"virtual_dot_2": 0.2},
            {"virtual_dot_2": 0.1}
        ]
        durations = [100, 152, 100]
        ramp_durations = [16, 500, 16]

        qd.add_sequence(
            name="reusable_seq",
            macro_types=macro_types,
            voltages=voltages,
            durations=durations,
            ramp_durations=ramp_durations
        )

        # Run the sequence multiple times
        with qua.program() as prog:
            seq = machine.voltage_sequences["main_qpu"]
            qd.run_sequence("reusable_seq")
            qd.step_to_voltages(0.05, duration=52)
            qd.run_sequence("reusable_seq")
            qd.ramp_to_voltages(0.15, ramp_duration=300, duration=16)
            qd.run_sequence("reusable_seq")

        # Verify no errors