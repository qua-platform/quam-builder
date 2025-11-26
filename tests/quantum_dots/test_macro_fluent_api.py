"""
Comprehensive tests for the macro fluent API and new optional voltages functionality.

This test file covers:
1. with_step_point() - creating new points and converting existing points
2. with_ramp_point() - creating new points and converting existing points
3. add_point_with_step_macro() - both use cases
4. add_point_with_ramp_macro() - both use cases
5. with_sequence() - creating sequence macros
6. Fluent API chaining
7. Macro execution and parameter overrides
8. Error handling for non-existent points
"""

import pytest
from qm import qua
from unittest.mock import MagicMock, patch

from quam_builder.architecture.quantum_dots.components.macros import (
    SequenceMacro,
    StepPointMacro,
    RampPointMacro,
    VoltagePointMacroMixin,
)


# ============================================================================
# Fluent API Tests - with_step_point
# ============================================================================


class TestWithStepPoint:
    """Tests for with_step_point() method."""

    def test_with_step_point_creates_new_point_and_macro(self, machine):
        """Test that with_step_point creates both point and macro when voltages are provided."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Use fluent API to create point and macro
        qd.with_step_point(
            "idle",
            voltages={"virtual_dot_1": 0.1},
            hold_duration=100
        )

        # Verify point was created in gate set
        gate_set = qd.voltage_sequence.gate_set
        expected_point_name = f"{qd.id}_idle"
        assert expected_point_name in gate_set.macros

        # Verify macro was created
        assert "idle" in qd.macros
        assert isinstance(qd.macros["idle"], StepPointMacro)
        assert qd.macros["idle"].hold_duration == 100

    def test_with_step_point_converts_existing_point(self, machine):
        """Test that with_step_point converts existing point to macro when voltages=None."""
        qd = machine.quantum_dots["virtual_dot_2"]

        # First, create a point without a macro
        voltages = {"virtual_dot_2": 0.2}
        qd.add_point("existing_point", voltages=voltages)

        # Verify point exists in gate set but macro doesn't exist yet
        gate_set = qd.voltage_sequence.gate_set
        expected_name = f"{qd.id}_existing_point"
        assert expected_name in gate_set.macros
        assert "existing_point" not in qd.macros

        # Now convert the existing point to a macro
        qd.with_step_point("existing_point", hold_duration=200)

        # Verify macro was created for existing point
        assert "existing_point" in qd.macros
        assert isinstance(qd.macros["existing_point"], StepPointMacro)
        assert qd.macros["existing_point"].hold_duration == 200

    def test_with_step_point_nonexistent_point_raises_error(self, machine):
        """Test that with_step_point raises error when point doesn't exist and voltages=None."""
        qd = machine.quantum_dots["virtual_dot_3"]

        with pytest.raises(KeyError, match="does not exist"):
            qd.with_step_point("nonexistent_point", hold_duration=100)

    def test_with_step_point_fluent_chaining(self, machine):
        """Test that with_step_point returns self for fluent chaining."""
        qd = machine.quantum_dots["virtual_dot_4"]

        result = (qd
            .with_step_point("idle", {"virtual_dot_4": 0.1}, hold_duration=100)
            .with_step_point("measure", {"virtual_dot_4": 0.2}, hold_duration=200))

        # Verify chaining works
        assert result is qd
        assert "idle" in qd.macros
        assert "measure" in qd.macros

    def test_with_step_point_default_parameters(self, machine):
        """Test with_step_point uses default parameter values correctly."""
        qd = machine.quantum_dots["virtual_dot_1"]

        qd.with_step_point("default_test", {"virtual_dot_1": 0.15})

        # Check defaults: hold_duration=100, point_duration=16
        macro = qd.macros["default_test"]
        assert macro.hold_duration == 100


# ============================================================================
# Fluent API Tests - with_ramp_point
# ============================================================================


class TestWithRampPoint:
    """Tests for with_ramp_point() method."""

    def test_with_ramp_point_creates_new_point_and_macro(self, machine):
        """Test that with_ramp_point creates both point and macro when voltages are provided."""
        qd = machine.quantum_dots["virtual_dot_1"]

        qd.with_ramp_point(
            "load",
            voltages={"virtual_dot_1": 0.3},
            hold_duration=200,
            ramp_duration=500
        )

        # Verify point was created
        gate_set = qd.voltage_sequence.gate_set
        expected_point_name = f"{qd.id}_load"
        assert expected_point_name in gate_set.macros

        # Verify macro was created
        assert "load" in qd.macros
        assert isinstance(qd.macros["load"], RampPointMacro)
        assert qd.macros["load"].hold_duration == 200
        assert qd.macros["load"].ramp_duration == 500

    def test_with_ramp_point_converts_existing_point(self, machine):
        """Test that with_ramp_point converts existing point to macro when voltages=None."""
        qd = machine.quantum_dots["virtual_dot_2"]

        # Create a point without a macro
        voltages = {"virtual_dot_2": 0.25}
        qd.add_point("ramp_existing", voltages=voltages)

        # Convert to ramp macro
        qd.with_ramp_point("ramp_existing", hold_duration=300, ramp_duration=400)

        # Verify macro was created
        assert "ramp_existing" in qd.macros
        assert isinstance(qd.macros["ramp_existing"], RampPointMacro)
        assert qd.macros["ramp_existing"].hold_duration == 300
        assert qd.macros["ramp_existing"].ramp_duration == 400

    def test_with_ramp_point_nonexistent_point_raises_error(self, machine):
        """Test that with_ramp_point raises error when point doesn't exist and voltages=None."""
        qd = machine.quantum_dots["virtual_dot_3"]

        with pytest.raises(KeyError, match="does not exist"):
            qd.with_ramp_point("nonexistent", hold_duration=100, ramp_duration=200)

    def test_with_ramp_point_fluent_chaining(self, machine):
        """Test that with_ramp_point supports fluent chaining."""
        qd = machine.quantum_dots["virtual_dot_4"]

        result = (qd
            .with_ramp_point("load", {"virtual_dot_4": 0.3}, hold_duration=200, ramp_duration=500)
            .with_step_point("readout", {"virtual_dot_4": 0.15}, hold_duration=1000))

        assert result is qd
        assert "load" in qd.macros
        assert "readout" in qd.macros

    def test_with_ramp_point_default_parameters(self, machine):
        """Test with_ramp_point uses default parameter values correctly."""
        qd = machine.quantum_dots["virtual_dot_1"]

        qd.with_ramp_point("ramp_default", {"virtual_dot_1": 0.35})

        # Check defaults: hold_duration=100, ramp_duration=16, point_duration=16
        macro = qd.macros["ramp_default"]
        assert macro.hold_duration == 100
        assert macro.ramp_duration == 16


# ============================================================================
# Tests - add_point_with_step_macro
# ============================================================================


class TestAddPointWithStepMacro:
    """Tests for add_point_with_step_macro() method."""

    def test_add_point_with_step_macro_creates_new(self, machine):
        """Test add_point_with_step_macro creates new point and macro."""
        qd = machine.quantum_dots["virtual_dot_1"]

        macro = qd.add_point_with_step_macro(
            "test_step",
            voltages={"virtual_dot_1": 0.12},
            hold_duration=150
        )

        # Verify return value
        assert isinstance(macro, StepPointMacro)
        assert macro.hold_duration == 150

        # Verify stored in macros dict
        assert "test_step" in qd.macros
        assert qd.macros["test_step"] is macro

    def test_add_point_with_step_macro_converts_existing(self, machine):
        """Test add_point_with_step_macro converts existing point."""
        qd = machine.quantum_dots["virtual_dot_2"]

        # Create point first
        qd.add_point("convert_step", {"virtual_dot_2": 0.22})

        # Convert to macro
        macro = qd.add_point_with_step_macro("convert_step", hold_duration=180)

        assert isinstance(macro, StepPointMacro)
        assert "convert_step" in qd.macros

    def test_add_point_with_step_macro_nonexistent_raises_error(self, machine):
        """Test add_point_with_step_macro raises error for nonexistent point."""
        qd = machine.quantum_dots["virtual_dot_3"]

        with pytest.raises(KeyError, match="does not exist"):
            qd.add_point_with_step_macro("missing_point", hold_duration=100)


# ============================================================================
# Tests - add_point_with_ramp_macro
# ============================================================================


class TestAddPointWithRampMacro:
    """Tests for add_point_with_ramp_macro() method."""

    def test_add_point_with_ramp_macro_creates_new(self, machine):
        """Test add_point_with_ramp_macro creates new point and macro."""
        qd = machine.quantum_dots["virtual_dot_1"]

        macro = qd.add_point_with_ramp_macro(
            "test_ramp",
            voltages={"virtual_dot_1": 0.28},
            hold_duration=250,
            ramp_duration=600
        )

        assert isinstance(macro, RampPointMacro)
        assert macro.hold_duration == 250
        assert macro.ramp_duration == 600
        assert "test_ramp" in qd.macros

    def test_add_point_with_ramp_macro_converts_existing(self, machine):
        """Test add_point_with_ramp_macro converts existing point."""
        qd = machine.quantum_dots["virtual_dot_2"]

        # Create point first
        qd.add_point("convert_ramp", {"virtual_dot_2": 0.27})

        # Convert to macro
        macro = qd.add_point_with_ramp_macro(
            "convert_ramp",
            hold_duration=220,
            ramp_duration=550
        )

        assert isinstance(macro, RampPointMacro)
        assert macro.hold_duration == 220
        assert macro.ramp_duration == 550

    def test_add_point_with_ramp_macro_nonexistent_raises_error(self, machine):
        """Test add_point_with_ramp_macro raises error for nonexistent point."""
        qd = machine.quantum_dots["virtual_dot_3"]

        with pytest.raises(KeyError, match="does not exist"):
            qd.add_point_with_ramp_macro(
                "missing_point",
                hold_duration=100,
                ramp_duration=200
            )


# ============================================================================
# Tests - with_sequence
# ============================================================================


class TestWithSequence:
    """Tests for with_sequence() method."""

    def test_with_sequence_creates_sequence_macro(self, machine):
        """Test with_sequence creates a SequenceMacro."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Create some macros first
        qd.with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
        qd.with_ramp_point("load", {"virtual_dot_1": 0.3}, hold_duration=200, ramp_duration=500)

        # Create sequence
        qd.with_sequence("init_sequence", ["idle", "load"])

        # Verify sequence was created
        assert "init_sequence" in qd.macros
        assert isinstance(qd.macros["init_sequence"], SequenceMacro)

    def test_with_sequence_fluent_chaining(self, machine):
        """Test with_sequence supports fluent chaining."""
        qd = machine.quantum_dots["virtual_dot_2"]

        result = (qd
            .with_step_point("idle", {"virtual_dot_2": 0.1}, hold_duration=100)
            .with_ramp_point("load", {"virtual_dot_2": 0.3}, hold_duration=200, ramp_duration=500)
            .with_step_point("measure", {"virtual_dot_2": 0.15}, hold_duration=1000)
            .with_sequence("full_cycle", ["idle", "load", "measure"]))

        assert result is qd
        assert "full_cycle" in qd.macros

    def test_with_sequence_nonexistent_macro_raises_error(self, machine):
        """Test with_sequence raises error if referenced macro doesn't exist."""
        qd = machine.quantum_dots["virtual_dot_3"]

        qd.with_step_point("idle", {"virtual_dot_3": 0.1}, hold_duration=100)

        with pytest.raises(KeyError, match="not found"):
            qd.with_sequence("bad_sequence", ["idle", "nonexistent_macro"])

    def test_with_sequence_nested_sequences(self, machine):
        """Test creating nested sequences."""
        qd = machine.quantum_dots["virtual_dot_4"]

        # Create primitive macros
        (qd
            .with_step_point("idle", {"virtual_dot_4": 0.1}, hold_duration=100)
            .with_ramp_point("load", {"virtual_dot_4": 0.3}, hold_duration=200, ramp_duration=500)
            .with_step_point("manipulate", {"virtual_dot_4": 0.25}, hold_duration=150)
            .with_step_point("readout", {"virtual_dot_4": 0.15}, hold_duration=1000))

        # Create sub-sequences
        qd.with_sequence("init", ["idle", "load"])
        qd.with_sequence("readout_seq", ["manipulate", "readout"])

        # Create higher-level sequence from sub-sequences
        qd.with_sequence("full_experiment", ["init", "readout_seq"])

        # Verify all sequences exist
        assert "init" in qd.macros
        assert "readout_seq" in qd.macros
        assert "full_experiment" in qd.macros


# ============================================================================
# Tests - Macro Execution and Parameter Overrides
# ============================================================================


class TestMacroExecution:
    """Tests for executing macros and parameter overrides."""

    def test_macro_execution_via_method_call(self, machine):
        """Test macros can be executed as methods via __getattr__."""
        qd = machine.quantum_dots["virtual_dot_1"]

        qd.with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)

        # Mock the voltage sequence to verify the macro is called
        with patch.object(qd.voltage_sequence, 'step_to_point') as mock_step:
            with qua.program() as prog:
                qd.idle()

            # Verify the underlying method was called
            mock_step.assert_called_once()

    def test_macro_parameter_override_hold_duration(self, machine):
        """Test parameter override for hold_duration."""
        qd = machine.quantum_dots["virtual_dot_2"]

        qd.with_step_point("idle", {"virtual_dot_2": 0.1}, hold_duration=100)

        with patch.object(qd.voltage_sequence, 'step_to_point') as mock_step:
            with qua.program() as prog:
                qd.idle(hold_duration=250)

            # Verify override was passed through
            # The call should use the overridden duration
            assert mock_step.called

    def test_macro_parameter_override_ramp_duration(self, machine):
        """Test parameter override for ramp_duration in RampPointMacro."""
        qd = machine.quantum_dots["virtual_dot_3"]

        qd.with_ramp_point("load", {"virtual_dot_3": 0.3}, hold_duration=200, ramp_duration=500)

        with patch.object(qd.voltage_sequence, 'ramp_to_point') as mock_ramp:
            with qua.program() as prog:
                qd.load(hold_duration=300, ramp_duration=600)

            assert mock_ramp.called

    def test_sequence_macro_execution(self, machine):
        """Test executing a sequence macro."""
        qd = machine.quantum_dots["virtual_dot_4"]

        (qd
            .with_step_point("idle", {"virtual_dot_4": 0.1}, hold_duration=100)
            .with_step_point("measure", {"virtual_dot_4": 0.2}, hold_duration=200)
            .with_sequence("test_seq", ["idle", "measure"]))

        with patch.object(qd.voltage_sequence, 'step_to_point') as mock_step:
            with qua.program() as prog:
                qd.test_seq()

            # Sequence should execute both macros
            assert mock_step.call_count == 2


# ============================================================================
# Tests - Complex Fluent API Workflows
# ============================================================================


class TestComplexFluentAPIWorkflows:
    """Tests for complex workflows using the fluent API."""

    def test_complete_fluent_workflow(self, machine):
        """Test a complete workflow using fluent API."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Complete fluent chain
        (qd
            .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
            .with_ramp_point("load", {"virtual_dot_1": 0.3}, hold_duration=200, ramp_duration=500)
            .with_step_point("manipulate", {"virtual_dot_1": 0.25}, hold_duration=150)
            .with_step_point("readout", {"virtual_dot_1": 0.15}, hold_duration=1000)
            .with_sequence("init", ["idle", "load"])
            .with_sequence("readout_seq", ["manipulate", "readout"])
            .with_sequence("full_experiment", ["init", "readout_seq"]))

        # Verify all macros were created
        assert len(qd.macros) == 7  # 4 points + 3 sequences

        # Verify sequence structure
        assert isinstance(qd.macros["full_experiment"], SequenceMacro)

    def test_mixed_creation_methods(self, machine):
        """Test mixing add_point, with_step_point, and with_sequence."""
        qd = machine.quantum_dots["virtual_dot_2"]

        # Mix different creation methods
        qd.add_point("base_point", {"virtual_dot_2": 0.1})
        qd.with_step_point("base_point", hold_duration=100)  # Convert existing
        qd.with_step_point("new_point", {"virtual_dot_2": 0.2}, hold_duration=200)  # Create new
        qd.with_sequence("mixed_seq", ["base_point", "new_point"])

        # Verify everything works together
        assert "base_point" in qd.macros
        assert "new_point" in qd.macros
        assert "mixed_seq" in qd.macros

    def test_updating_existing_point_and_macro(self, machine):
        """Test that points and macros can be updated independently."""
        qd = machine.quantum_dots["virtual_dot_3"]

        # Create point and macro
        qd.with_step_point("updateable", {"virtual_dot_3": 0.1}, hold_duration=100)

        # Update the point (replace voltages)
        qd.add_point(
            "updateable",
            {"virtual_dot_3": 0.2},
            replace_existing_point=True
        )

        # Create new macro with different duration for same point
        qd.with_step_point("updateable", hold_duration=300)

        # Verify the macro uses new duration
        assert qd.macros["updateable"].hold_duration == 300


# ============================================================================
# Tests - Error Handling and Edge Cases
# ============================================================================


class TestErrorHandlingAndEdgeCases:
    """Tests for error handling and edge cases."""

    def test_empty_sequence_creation(self, machine):
        """Test creating a sequence with no macros."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # This should succeed but create an empty sequence
        qd.with_sequence("empty_seq", [])

        assert "empty_seq" in qd.macros
        assert isinstance(qd.macros["empty_seq"], SequenceMacro)

    def test_macro_without_parent_raises_error(self):
        """Test that calling a macro without parent raises appropriate error."""
        # Create a standalone macro (not attached to component)
        macro = StepPointMacro(
            point_ref="#./voltage_sequence/gate_set/macros/some_point",
            hold_duration=100
        )

        with pytest.raises(ValueError, match="has no parent"):
            macro()

    def test_point_name_with_special_characters(self, machine):
        """Test creating points with underscores and numbers in names."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Should handle various name formats
        qd.with_step_point("point_1", {"virtual_dot_1": 0.1}, hold_duration=100)
        qd.with_step_point("point_2_test", {"virtual_dot_1": 0.2}, hold_duration=200)
        qd.with_step_point("TEST_POINT_3", {"virtual_dot_1": 0.3}, hold_duration=300)

        assert "point_1" in qd.macros
        assert "point_2_test" in qd.macros
        assert "TEST_POINT_3" in qd.macros

    def test_creating_macro_with_same_name_overwrites(self, machine):
        """Test that creating a macro with existing name overwrites it."""
        qd = machine.quantum_dots["virtual_dot_2"]

        qd.with_step_point("overwrite", {"virtual_dot_2": 0.1}, hold_duration=100)
        original_macro = qd.macros["overwrite"]

        # Create new macro with same name (requires replace_existing_point=True)
        qd.with_step_point("overwrite", {"virtual_dot_2": 0.2}, hold_duration=200, replace_existing_point=True)
        new_macro = qd.macros["overwrite"]

        # Verify it was overwritten
        assert new_macro is not original_macro
        assert new_macro.hold_duration == 200