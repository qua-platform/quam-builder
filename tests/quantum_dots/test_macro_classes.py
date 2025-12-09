"""
Comprehensive tests for macro classes: StepPointMacro, RampPointMacro, and SequenceMacro.

This test file covers:
1. StepPointMacro - creation, execution, reference resolution
2. RampPointMacro - creation, execution, reference resolution
3. SequenceMacro - creation, composition, nested sequences
4. Macro serialization and reference system
5. Parameter overrides
6. Error handling
"""

import pytest
from qm import qua
from unittest.mock import patch

from quam_builder.tools.macros.point_macros import (
    SequenceMacro,
    StepPointMacro,
    RampPointMacro,
    VoltagePointMacroMixin,
)


# ============================================================================
# StepPointMacro Tests
# ============================================================================


class TestStepPointMacro:
    """Tests for StepPointMacro class."""

    def test_step_point_macro_creation(self, machine):
        """Test creating a StepPointMacro."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Create point first
        qd.add_point("test_point", {"virtual_dot_1": 0.1})
        point_ref = f"#./voltage_sequence/gate_set/macros/{qd.id}_test_point"

        # Create macro
        macro = StepPointMacro(
            point_ref=point_ref,
            hold_duration=100
        )

        assert macro.point_ref == point_ref
        assert macro.hold_duration == 100
        assert macro.macro_type == "step"

    def test_step_point_macro_inferred_duration(self, machine):
        """Test inferred_duration property of StepPointMacro."""
        qd = machine.quantum_dots["virtual_dot_1"]
        qd.add_point("test", {"virtual_dot_1": 0.1})

        macro = qd.add_point_with_step_macro("test_duration", {"virtual_dot_1": 0.1}, hold_duration=1000)

        # Duration should be in seconds (use pytest.approx for floating point comparison)
        assert macro.inferred_duration == pytest.approx(1000 * 1e-9)
        assert macro.inferred_duration == pytest.approx(1e-6)  # 1000ns = 1us

    def test_step_point_macro_apply_method(self, machine):
        """Test StepPointMacro.apply() executes correctly."""
        qd = machine.quantum_dots["virtual_dot_1"]
        qd.with_step_point("apply_test", {"virtual_dot_1": 0.1}, hold_duration=100)

        macro = qd.macros["apply_test"]

        with patch.object(qd.voltage_sequence, 'step_to_point') as mock_step:
            with qua.program() as prog:
                macro.apply()

            # Verify step_to_point was called with correct point name
            mock_step.assert_called_once()
            call_args = mock_step.call_args
            assert f"{qd.id}_apply_test" in str(call_args)

    def test_step_point_macro_apply_with_override(self, machine):
        """Test StepPointMacro.apply() with parameter override."""
        qd = machine.quantum_dots["virtual_dot_2"]
        qd.with_step_point("override_test", {"virtual_dot_2": 0.2}, hold_duration=100)

        macro = qd.macros["override_test"]

        with patch.object(qd.voltage_sequence, 'step_to_point') as mock_step:
            with qua.program() as prog:
                macro.apply(hold_duration=250)

            assert mock_step.called

    def test_step_point_macro_callable_interface(self, machine):
        """Test StepPointMacro can be called as a function."""
        qd = machine.quantum_dots["virtual_dot_3"]
        qd.with_step_point("callable_test", {"virtual_dot_3": 0.3}, hold_duration=100)

        macro = qd.macros["callable_test"]

        with patch.object(qd.voltage_sequence, 'step_to_point') as mock_step:
            with qua.program() as prog:
                macro()  # Call as function

            assert mock_step.called

    def test_step_point_macro_get_point_name(self, machine):
        """Test _get_point_name() extracts point name from reference."""
        qd = machine.quantum_dots["virtual_dot_1"]
        qd.with_step_point("name_test", {"virtual_dot_1": 0.1}, hold_duration=100)

        macro = qd.macros["name_test"]
        point_name = macro._get_point_name()

        assert point_name == f"{qd.id}_name_test"


# ============================================================================
# RampPointMacro Tests
# ============================================================================


class TestRampPointMacro:
    """Tests for RampPointMacro class."""

    def test_ramp_point_macro_creation(self, machine):
        """Test creating a RampPointMacro."""
        qd = machine.quantum_dots["virtual_dot_1"]

        qd.add_point("ramp_test", {"virtual_dot_1": 0.3})
        point_ref = f"#./voltage_sequence/gate_set/macros/{qd.id}_ramp_test"

        macro = RampPointMacro(
            point_ref=point_ref,
            hold_duration=200,
            ramp_duration=500
        )

        assert macro.point_ref == point_ref
        assert macro.hold_duration == 200
        assert macro.ramp_duration == 500
        assert macro.macro_type == "ramp"

    def test_ramp_point_macro_inferred_duration(self, machine):
        """Test inferred_duration property includes ramp + hold."""
        qd = machine.quantum_dots["virtual_dot_1"]

        macro = qd.add_point_with_ramp_macro(
            "ramp_duration",
            {"virtual_dot_1": 0.3},
            hold_duration=200,
            ramp_duration=500
        )

        # Should be ramp + hold in seconds
        expected_duration = (500 + 200) * 1e-9
        assert macro.inferred_duration == expected_duration

    def test_ramp_point_macro_apply_method(self, machine):
        """Test RampPointMacro.apply() executes correctly."""
        qd = machine.quantum_dots["virtual_dot_2"]
        qd.with_ramp_point("ramp_apply", {"virtual_dot_2": 0.25}, hold_duration=200, ramp_duration=500)

        macro = qd.macros["ramp_apply"]

        with patch.object(qd.voltage_sequence, 'ramp_to_point') as mock_ramp:
            with qua.program() as prog:
                macro.apply()

            mock_ramp.assert_called_once()

    def test_ramp_point_macro_apply_with_overrides(self, machine):
        """Test RampPointMacro.apply() with both hold and ramp overrides."""
        qd = machine.quantum_dots["virtual_dot_3"]
        qd.with_ramp_point("override_ramp", {"virtual_dot_3": 0.28}, hold_duration=200, ramp_duration=500)

        macro = qd.macros["override_ramp"]

        with patch.object(qd.voltage_sequence, 'ramp_to_point') as mock_ramp:
            with qua.program() as prog:
                macro.apply(hold_duration=300, ramp_duration=600)

            assert mock_ramp.called

    def test_ramp_point_macro_default_ramp_duration(self, machine):
        """Test RampPointMacro uses default ramp_duration=16."""
        qd = machine.quantum_dots["virtual_dot_1"]

        macro = qd.add_point_with_ramp_macro(
            "default_ramp",
            {"virtual_dot_1": 0.2},
            hold_duration=100
            # ramp_duration not specified, should default to 16
        )

        assert macro.ramp_duration == 16


# ============================================================================
# SequenceMacro Tests
# ============================================================================


class TestSequenceMacro:
    """Tests for SequenceMacro class."""

    def test_sequence_macro_creation(self):
        """Test creating a SequenceMacro."""
        seq = SequenceMacro(name="test_seq", macro_refs=())

        assert seq.name == "test_seq"
        assert seq.macro_refs == ()
        assert seq.description is None

    def test_sequence_macro_with_description(self):
        """Test SequenceMacro with description."""
        seq = SequenceMacro(
            name="test_seq",
            macro_refs=(),
            description="Test sequence for experiments"
        )

        assert seq.description == "Test sequence for experiments"

    def test_sequence_macro_with_reference(self):
        """Test SequenceMacro.with_reference() method."""
        seq = SequenceMacro(name="test_seq", macro_refs=())

        new_seq = seq.with_reference("#./macros/idle")

        # Should return new instance
        assert new_seq is not seq
        assert new_seq.macro_refs == ("#./macros/idle",)
        # Original unchanged
        assert seq.macro_refs == ()

    def test_sequence_macro_with_multiple_references(self):
        """Test chaining with_reference() calls."""
        seq = SequenceMacro(name="test_seq", macro_refs=())

        new_seq = (seq
            .with_reference("#./macros/idle")
            .with_reference("#./macros/load")
            .with_reference("#./macros/measure"))

        assert len(new_seq.macro_refs) == 3
        assert new_seq.macro_refs[0] == "#./macros/idle"
        assert new_seq.macro_refs[1] == "#./macros/load"
        assert new_seq.macro_refs[2] == "#./macros/measure"

    def test_sequence_macro_with_macro_helper(self, machine):
        """Test SequenceMacro.with_macro() helper method."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Create some macros
        qd.with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)

        # Create sequence using with_macro
        seq = SequenceMacro(name="test_seq", macro_refs=())
        new_seq = seq.with_macro(qd, "idle")

        assert len(new_seq.macro_refs) == 1
        assert "#./macros/idle" in new_seq.macro_refs[0]

    def test_sequence_macro_with_macros_helper(self, machine):
        """Test SequenceMacro.with_macros() helper method."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Create macros
        (qd
            .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
            .with_step_point("load", {"virtual_dot_1": 0.3}, hold_duration=200)
            .with_step_point("measure", {"virtual_dot_1": 0.15}, hold_duration=300))

        # Create sequence using with_macros (plural)
        seq = SequenceMacro(name="test_seq", macro_refs=())
        new_seq = seq.with_macros(qd, ["idle", "load", "measure"])

        assert len(new_seq.macro_refs) == 3

    def test_sequence_macro_resolved_macros(self, machine):
        """Test SequenceMacro.resolved_macros() resolves references."""
        qd = machine.quantum_dots["virtual_dot_1"]

        (qd
            .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
            .with_step_point("measure", {"virtual_dot_1": 0.2}, hold_duration=200)
            .with_sequence("test_seq", ["idle", "measure"]))

        seq_macro = qd.macros["test_seq"]
        resolved = seq_macro.resolved_macros(qd)

        # Should resolve to actual macro objects
        assert len(resolved) == 2
        assert isinstance(resolved[0], StepPointMacro)
        assert isinstance(resolved[1], StepPointMacro)

    def test_sequence_macro_apply_executes_all(self, machine):
        """Test SequenceMacro.apply() executes all macros in sequence."""
        qd = machine.quantum_dots["virtual_dot_1"]

        (qd
            .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
            .with_step_point("measure", {"virtual_dot_1": 0.2}, hold_duration=200)
            .with_sequence("test_seq", ["idle", "measure"]))

        with patch.object(qd.voltage_sequence, 'step_to_point') as mock_step:
            with qua.program() as prog:
                qd.test_seq()

            # Should call step_to_point twice
            assert mock_step.call_count == 2

    def test_sequence_macro_callable_interface(self, machine):
        """Test SequenceMacro can be called as a function."""
        qd = machine.quantum_dots["virtual_dot_2"]

        (qd
            .with_step_point("idle", {"virtual_dot_2": 0.1}, hold_duration=100)
            .with_sequence("callable_seq", ["idle"]))

        seq_macro = qd.macros["callable_seq"]

        with patch.object(qd.voltage_sequence, 'step_to_point') as mock_step:
            with qua.program() as prog:
                seq_macro()  # Call as function

            assert mock_step.called

    def test_sequence_macro_total_duration(self, machine):
        """Test SequenceMacro.total_duration_seconds() sums durations."""
        qd = machine.quantum_dots["virtual_dot_1"]

        (qd
            .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=1000)  # 1000ns
            .with_step_point("measure", {"virtual_dot_1": 0.2}, hold_duration=2000)  # 2000ns
            .with_sequence("timed_seq", ["idle", "measure"]))

        seq_macro = qd.macros["timed_seq"]
        total_duration = seq_macro.total_duration_seconds(qd)

        # Should be (1000 + 2000) * 1e-9 = 3e-6 seconds
        assert total_duration == pytest.approx(3000 * 1e-9)

    def test_nested_sequence_execution(self, machine):
        """Test nested sequences execute correctly."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Create primitive macros
        (qd
            .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
            .with_step_point("load", {"virtual_dot_1": 0.3}, hold_duration=200)
            .with_step_point("manipulate", {"virtual_dot_1": 0.25}, hold_duration=150)
            .with_step_point("readout", {"virtual_dot_1": 0.15}, hold_duration=300))

        # Create sub-sequences
        qd.with_sequence("init", ["idle", "load"])
        qd.with_sequence("readout_seq", ["manipulate", "readout"])

        # Create top-level sequence
        qd.with_sequence("full_experiment", ["init", "readout_seq"])

        with patch.object(qd.voltage_sequence, 'step_to_point') as mock_step:
            with qua.program() as prog:
                qd.full_experiment()

            # Should execute all 4 primitive operations
            assert mock_step.call_count == 4


# ============================================================================
# Macro Reference System Tests
# ============================================================================


class TestMacroReferenceSystem:
    """Tests for the macro reference system."""

    def test_point_reference_creation(self, machine):
        """Test that point references are created correctly."""
        qd = machine.quantum_dots["virtual_dot_1"]

        qd.with_step_point("ref_test", {"virtual_dot_1": 0.1}, hold_duration=100)

        macro = qd.macros["ref_test"]

        # Get raw reference string (bypass QUAM's automatic resolution)
        point_ref_raw = object.__getattribute__(macro, "__dict__").get("point_ref")

        # Reference should point to gate set macros
        assert point_ref_raw is not None
        assert isinstance(point_ref_raw, str)
        assert "/macros/" in point_ref_raw
        assert f"{qd.id}_ref_test" in point_ref_raw

    def test_macro_reference_in_sequence(self, machine):
        """Test that sequence macros store references to other macros."""
        qd = machine.quantum_dots["virtual_dot_1"]

        (qd
            .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
            .with_sequence("test_seq", ["idle"]))

        seq_macro = qd.macros["test_seq"]

        # Sequence should store reference string
        assert len(seq_macro.macro_refs) == 1
        assert isinstance(seq_macro.macro_refs[0], str)
        assert "#./macros/idle" in seq_macro.macro_refs[0]

    def test_reference_resolution_after_modification(self, machine):
        """Test that references resolve correctly even after point modification."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Create point and macro
        qd.with_step_point("changeable", {"virtual_dot_1": 0.1}, hold_duration=100)

        # Modify the point
        qd.add_point("changeable", {"virtual_dot_1": 0.2}, replace_existing_point=True)

        # Reference should still resolve
        macro = qd.macros["changeable"]
        with patch.object(qd.voltage_sequence, 'step_to_point'):
            with qua.program() as prog:
                macro.apply()  # Should not raise error


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestMacroErrorHandling:
    """Tests for error handling in macros."""

    def test_macro_without_parent_error(self):
        """Test that calling macro without parent raises error."""
        macro = StepPointMacro(
            point_ref="#./voltage_sequence/gate_set/macros/test",
            hold_duration=100
        )

        with pytest.raises(ValueError, match="has no parent"):
            macro()

    def test_sequence_invalid_reference_error(self, machine):
        """Test that SequenceMacro raises error for invalid reference."""
        qd = machine.quantum_dots["virtual_dot_1"]

        qd.with_step_point("valid", {"virtual_dot_1": 0.1}, hold_duration=100)

        # Manually create sequence with invalid reference
        seq = SequenceMacro(name="bad_seq", macro_refs=("#./macros/nonexistent",))
        qd.macros["bad_seq"] = seq

        from quam.utils.exceptions import InvalidReferenceError

        with pytest.raises(InvalidReferenceError):
            with qua.program() as prog:
                seq.apply()

    def test_sequence_with_nonexistent_macro_error(self, machine):
        """Test with_sequence raises error for nonexistent macro."""
        qd = machine.quantum_dots["virtual_dot_1"]

        qd.with_step_point("exists", {"virtual_dot_1": 0.1}, hold_duration=100)

        with pytest.raises(KeyError, match="not found"):
            qd.with_sequence("bad_seq", ["exists", "does_not_exist"])

    def test_invalid_point_reference_format(self, machine):
        """Test that invalid point reference format is handled."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Create macro with malformed reference
        macro = StepPointMacro(
            point_ref="invalid_reference_format",
            hold_duration=100
        )
        qd.macros["bad_macro"] = macro

        # The _get_point_name should return the last segment even for invalid format
        # It will only fail when trying to resolve the reference later
        point_name = macro._get_point_name()
        assert point_name == "invalid_reference_format"


# ============================================================================
# Serialization Tests
# ============================================================================


class TestMacroSerialization:
    """Tests for macro serialization and deserialization."""

    def test_step_point_macro_serializable(self, machine):
        """Test that StepPointMacro can be serialized."""
        qd = machine.quantum_dots["virtual_dot_1"]

        qd.with_step_point("serialize_test", {"virtual_dot_1": 0.1}, hold_duration=100)

        # Get the macro
        macro = qd.macros["serialize_test"]

        # Check it has serializable attributes (get raw value to avoid QUAM's auto-resolution)
        point_ref_raw = object.__getattribute__(macro, "__dict__").get("point_ref")
        assert point_ref_raw is not None
        assert isinstance(point_ref_raw, str)
        assert isinstance(macro.hold_duration, int)

    def test_ramp_point_macro_serializable(self, machine):
        """Test that RampPointMacro can be serialized."""
        qd = machine.quantum_dots["virtual_dot_1"]

        qd.with_ramp_point("ramp_serialize", {"virtual_dot_1": 0.3}, hold_duration=200, ramp_duration=500)

        macro = qd.macros["ramp_serialize"]

        # Get raw reference string (bypass QUAM's automatic resolution)
        point_ref_raw = object.__getattribute__(macro, "__dict__").get("point_ref")
        assert isinstance(point_ref_raw, str)
        assert isinstance(macro.hold_duration, int)
        assert isinstance(macro.ramp_duration, int)

    def test_sequence_macro_serializable(self, machine):
        """Test that SequenceMacro can be serialized."""
        qd = machine.quantum_dots["virtual_dot_1"]

        (qd
            .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
            .with_sequence("seq_serialize", ["idle"]))

        seq = qd.macros["seq_serialize"]

        # Should only contain serializable types
        assert isinstance(seq.name, str)
        assert isinstance(seq.macro_refs, tuple)
        assert all(isinstance(ref, str) for ref in seq.macro_refs)


# ============================================================================
# Integration Tests
# ============================================================================


class TestMacroIntegration:
    """Integration tests for complete macro workflows."""

    def test_complete_experiment_workflow(self, machine):
        """Test a complete experimental workflow with macros."""
        qd = machine.quantum_dots["virtual_dot_1"]

        # Define complete workflow using fluent API
        (qd
            .with_step_point("idle", {"virtual_dot_1": 0.05}, hold_duration=100)
            .with_ramp_point("initialize", {"virtual_dot_1": 0.15}, hold_duration=200, ramp_duration=500)
            .with_step_point("manipulate", {"virtual_dot_1": 0.25}, hold_duration=150)
            .with_ramp_point("readout_pos", {"virtual_dot_1": 0.12}, hold_duration=300, ramp_duration=400)
            .with_sequence("initialization", ["idle", "initialize"])
            .with_sequence("measurement", ["manipulate", "readout_pos"])
            .with_sequence("full_experiment", ["initialization", "measurement"]))

        # Execute complete experiment
        with patch.object(qd.voltage_sequence, 'step_to_point') as mock_step:
            with patch.object(qd.voltage_sequence, 'ramp_to_point') as mock_ramp:
                with qua.program() as prog:
                    qd.full_experiment()

                # Verify all operations were executed
                assert mock_step.call_count == 2  # idle, manipulate
                assert mock_ramp.call_count == 2  # initialize, readout_pos

    def test_workflow_with_parameter_overrides(self, machine):
        """Test workflow where parameters are overridden at runtime."""
        qd = machine.quantum_dots["virtual_dot_2"]

        (qd
            .with_step_point("base", {"virtual_dot_2": 0.1}, hold_duration=100)
            .with_ramp_point("target", {"virtual_dot_2": 0.3}, hold_duration=200, ramp_duration=500))

        with patch.object(qd.voltage_sequence, 'step_to_point'):
            with patch.object(qd.voltage_sequence, 'ramp_to_point'):
                with qua.program() as prog:
                    # Use default parameters
                    qd.base()
                    qd.target()

                    # Override parameters
                    qd.base(hold_duration=150)
                    qd.target(hold_duration=300, ramp_duration=700)