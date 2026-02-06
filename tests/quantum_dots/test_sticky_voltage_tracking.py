"""
Test for sticky voltage tracking during non-voltage operations.

This test demonstrates that the current implementation doesn't track
voltage compensation correctly when non-voltage macros (like x180) execute
while voltages are held at a sticky level.

The test creates a scenario where:
1. A voltage is set to a non-zero value with a known duration
2. A non-voltage macro (like x180) executes with a known duration
3. The voltage remains "sticky" during the non-voltage operation
4. The integrated voltage should account for BOTH durations

Current behavior: Only the voltage macro duration is tracked
Expected behavior (after fix): Both voltage and non-voltage macro durations should be tracked
"""

import pytest
from qm import qua
from quam.components.macro import QubitMacro
from quam.components import StickyChannelAddon
from quam.components.ports import LFFEMAnalogOutputPort

from quam_builder.architecture.quantum_dots.components import VoltageGate, QuantumDot
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD


@pytest.fixture
def simple_machine():
    """
    Creates a minimal BaseQuamQD machine for testing voltage tracking.
    Avoids the complexity of the full conftest machine fixture.
    """
    machine = BaseQuamQD()
    lf_fem = 6

    # Create a single plunger gate
    p1 = VoltageGate(
        id="plunger_1",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem, port_id=1),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

    # Create Virtual Gate Set (minimal - just one gate)
    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": p1,
        },
        gate_set_id="test_qpu",
    )

    # Register Quantum Dot
    machine.register_channel_elements(
        plunger_channels=[p1],
        barrier_channels=[],
        sensor_channels_resonators=[],
    )

    return machine


# Mock non-voltage macro with known duration
class MockX180Macro(QubitMacro):
    """Mock X180 macro that represents a qubit rotation (no voltage channels)."""

    @property
    def inferred_duration(self):
        """Return duration in seconds (100ns)."""
        return 100e-9  # 100 nanoseconds

    def apply(self, **kwargs):
        """Mock apply that does nothing (simulates RF-only operation)."""
        # In reality, this would play on RF channels, not voltage channels
        pass


class TestStickyVoltageTracking:
    """Tests for sticky voltage tracking during non-voltage operations."""

    def test_voltage_tracking_without_non_voltage_operation(self, simple_machine):
        """
        Baseline test: Voltage tracking works correctly for voltage-only operations.

        This test verifies that the basic voltage tracking works as expected
        when only voltage macros are used.
        """
        qd = simple_machine.quantum_dots["virtual_dot_1"]

        # Create a voltage point and step macro
        qd.add_point_with_step_macro(
            "baseline_voltage",
            {"virtual_dot_1": 0.1},
            hold_duration=100  # 100ns at 0.1V
        )

        # Execute just the voltage step
        with qua.program() as prog:
            qd.baseline_voltage()

        # Check the integrated voltage tracking
        # Note: Trackers use physical channel names, not virtual gate names
        tracker = qd.voltage_sequence.state_trackers["plunger_1"]

        SCALING_FACTOR = 1024  # From sequence_state_tracker.py
        expected_integrated_voltage = int(0.1 * 100 * SCALING_FACTOR)  # 10240

        assert tracker.integrated_voltage == expected_integrated_voltage, \
            f"Baseline voltage tracking failed. Expected {expected_integrated_voltage}, got {tracker.integrated_voltage}"

    def test_sticky_voltage_tracking_with_non_voltage_operation(self, simple_machine):
        """
        Test that sticky voltage tracking works correctly with non-voltage operations.

        Scenario:
        1. Apply a voltage step (100ns at 0.1V) - integrated voltage tracked correctly
        2. Execute x180 macro (100ns duration) while voltage is sticky at 0.1V
        3. Integrated voltage should include BOTH durations: (100ns + 100ns) * 0.1V * 1024

        Fixed behavior: Both 100ns periods are tracked automatically
        """
        qd = simple_machine.quantum_dots["virtual_dot_1"]

        # Create a voltage point and step macro
        qd.add_point_with_step_macro(
            "sticky_voltage",
            {"virtual_dot_1": 0.1},
            hold_duration=100  # 100ns at 0.1V
        )

        # Add a mock x180 macro with known duration
        qd.macros["x180"] = MockX180Macro()

        # Execute the sequence
        with qua.program() as prog:
            # Apply voltage step - this sets voltage to 0.1V for 100ns
            qd.sticky_voltage()

            # Execute x180 - voltage is sticky at 0.1V for another 100ns
            # but the voltage tracker doesn't know about this duration
            qd.x180()

        # Check the integrated voltage tracking
        tracker = qd.voltage_sequence.state_trackers["plunger_1"]

        SCALING_FACTOR = 1024  # From sequence_state_tracker.py

        # Expected (correct) behavior: Both step and x180 durations should be tracked
        expected_correct_value = int(0.1 * (100 + 100) * SCALING_FACTOR)  # 20480

        # This assertion should fail with current implementation (demonstrating the bug)
        # After the fix, remove the @pytest.mark.xfail decorator and this should pass
        assert tracker.integrated_voltage == expected_correct_value, \
            f"Integrated voltage should include non-voltage macro duration. " \
            f"Expected {expected_correct_value}, got {tracker.integrated_voltage}"

    def test_complex_sequence_with_multiple_non_voltage_operations(self, simple_machine):
        """
        Test a more complex scenario with multiple voltage and non-voltage operations.

        Sequence:
        1. Voltage at 0.1V for 100ns
        2. x180 (100ns) - sticky at 0.1V
        3. Voltage at 0.2V for 52ns
        4. x180 (100ns) - sticky at 0.2V
        5. Voltage back to 0V

        Expected integrated voltage:
        - 0.1V * (100ns + 100ns) = 0.1V * 200ns
        - 0.2V * (52ns + 100ns) = 0.2V * 152ns
        - Total: (0.1*200 + 0.2*152) = 50.4 V*ns
        - Scaled: 50.4 * 1024 = 51610 (rounded to int)
        """
        qd = simple_machine.quantum_dots["virtual_dot_1"]

        # Create voltage points
        qd.add_point_with_step_macro("voltage_1", {"virtual_dot_1": 0.1}, hold_duration=100)
        qd.add_point_with_step_macro("voltage_2", {"virtual_dot_1": 0.2}, hold_duration=52)
        qd.add_point_with_step_macro("voltage_zero", {"virtual_dot_1": 0.0}, hold_duration=16)

        # Add mock x180 macro
        qd.macros["x180"] = MockX180Macro()

        with qua.program() as prog:
            qd.voltage_1()  # 0.1V for 100ns
            qd.x180()       # sticky at 0.1V for 100ns (BUG: not tracked)
            qd.voltage_2()  # 0.2V for 50ns (also steps from 0.1V to 0.2V)
            qd.x180()       # sticky at 0.2V for 100ns (BUG: not tracked)
            qd.voltage_zero()  # Back to 0V

        tracker = qd.voltage_sequence.state_trackers["plunger_1"]

        SCALING_FACTOR = 1024

        # Previous buggy behavior: only voltage macro durations tracked
        # expected_buggy_value = int((0.1 * 100 + 0.2 * 52 + 0.0 * 16) * SCALING_FACTOR)  # 20889 (rounded)

        # Fixed behavior: all durations tracked (including non-voltage macros)
        expected_correct_value = int((0.1 * (100 + 100) + 0.2 * (52 + 100) + 0.0 * 16) * SCALING_FACTOR)  # 51610

        # After fix: verify correct behavior
        # Note: Actual value may differ by 1 due to incremental rounding in np.round
        assert abs(tracker.integrated_voltage - expected_correct_value) <= 1, \
            f"After fix: integrated voltage should be {expected_correct_value}, got {tracker.integrated_voltage}"

    def test_sticky_voltage_tracking_only_affects_non_zero_voltages(self, simple_machine):
        """
        Verify that sticky voltage tracking only matters when voltage is non-zero.

        If voltage is at 0V and a non-voltage macro executes, integrated voltage
        should not change (0V * duration = 0).
        """
        qd = simple_machine.quantum_dots["virtual_dot_1"]

        # Create a zero voltage point
        qd.add_point_with_step_macro("voltage_zero", {"virtual_dot_1": 0.0}, hold_duration=100)

        # Add mock x180 macro
        qd.macros["x180"] = MockX180Macro()

        with qua.program() as prog:
            qd.voltage_zero()  # 0.0V for 100ns
            qd.x180()          # sticky at 0.0V for 100ns

        tracker = qd.voltage_sequence.state_trackers["plunger_1"]

        # Integrated voltage should be 0 (or very close to 0)
        assert tracker.integrated_voltage == 0, \
            f"Zero voltage should result in zero integrated voltage, got {tracker.integrated_voltage}"
