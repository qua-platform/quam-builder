"""
Comprehensive examples demonstrating voltage point and sequence macro functionality.

This module showcases all the ways to create, compose, and execute voltage point macros
in the quantum dot architecture, including:

1. **Point Macros**: StepPointMacro and RampPointMacro for voltage operations
2. **Sequence Macros**: Composing multiple macros into reusable sequences
3. **Fluent API**: Method chaining for clean macro definition
4. **Dynamic Method Calling**: Using __getattr__ to call macros as methods
5. **Parameter Overrides**: Runtime customization of macro parameters
6. **Serialization**: All approaches are QuAM-serialization compatible

Key Features:
- Flexibility: Define macros dynamically during calibration
- Clean API: Call macros as methods like @register_macro decorated functions
- Composability: Build complex sequences from simple primitives
- Serializable: All state stored in self.macros dict
"""

from typing import Dict
from dataclasses import field

from quam.core import quam_dataclass, QuamComponent
from qm import qua

from .macros import (
    SequenceMacro,
    StepPointMacro,
    RampPointMacro,
    VoltagePointMacroMixin,
)


# ============================================================================
# Example Component Setup
# ============================================================================

@quam_dataclass
class ExampleQuantumDot(VoltagePointMacroMixin):
    """
    Example quantum dot component demonstrating macro functionality.

    In practice, this would be a QuantumDot, QuantumDotPair, LDQubit, or
    LDQubitPair component that inherits from VoltagePointMacroMixin.
    """

    id: str
    _voltage_sequence: any = None  # In real usage, this would be a VoltageSequence

    @property
    def voltage_sequence(self):
        """Return the voltage sequence (placeholder for example)."""
        return self._voltage_sequence

    def __post_init__(self):
        # Initialize VoltagePointMacroMixin
        super().__post_init__()


# ============================================================================
# Example 1: Traditional API (Backward Compatible)
# ============================================================================

def example_01_traditional_api(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Traditional approach: Manual point and macro creation.

    This is the original API, still fully supported for backward compatibility.
    Useful when you need fine-grained control over each step.
    """
    # Step 1: Add voltage point to gate set
    quantum_dot.add_point(
        point_name="idle",
        voltages={"virtual_dot_0": 0.1},
        duration=16
    )

    # Step 2: Get reference to the point
    point = quantum_dot.voltage_sequence.gate_set.macros[f"{quantum_dot.id}_idle"]
    point_ref = point.get_reference()

    # Step 3: Create macro with reference
    idle_macro = StepPointMacro(
        point_ref=point_ref,
        hold_duration=100
    )

    # Step 4: Store macro and set parent
    quantum_dot.macros["idle"] = idle_macro
    idle_macro.parent = quantum_dot

    # Execute: Traditional dictionary access
    quantum_dot.macros["idle"]()

    # Or with parameter override
    quantum_dot.macros["idle"](hold_duration=200)


# ============================================================================
# Example 2: Helper Methods (Recommended Traditional Approach)
# ============================================================================

def example_02_helper_methods(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Using convenience helper methods that combine point and macro creation.

    This is the recommended approach when not using the fluent API.
    Automatically handles point creation, reference setup, and parent linking.
    """
    # Create point + step macro in one call
    quantum_dot.add_point_with_step_macro(
        macro_name="idle",
        voltages={"virtual_dot_0": 0.1},
        hold_duration=100,
        point_duration=16
    )

    # Create point + ramp macro in one call
    quantum_dot.add_point_with_ramp_macro(
        macro_name="load",
        voltages={"virtual_dot_0": 0.3},
        hold_duration=200,
        ramp_duration=500,
        point_duration=16
    )

    # Execute via dictionary access
    quantum_dot.macros["idle"]()
    quantum_dot.macros["load"]()

    # Create a sequence macro manually
    sequence = SequenceMacro(name="init_sequence")
    sequence = sequence.with_macros(quantum_dot, ["idle", "load"])
    quantum_dot.macros["init_sequence"] = sequence
    sequence.parent = quantum_dot

    # Execute the sequence
    quantum_dot.macros["init_sequence"]()


# ============================================================================
# Example 3: Fluent API (Recommended Modern Approach)
# ============================================================================

def example_03_fluent_api(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Modern fluent API with method chaining.

    This is the RECOMMENDED approach for new code. Provides:
    - Clean, readable syntax
    - Method chaining for multiple macros
    - Automatic reference and parent setup
    - Full serialization support
    """
    # Define multiple macros in one fluent chain
    (quantum_dot
        .with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)
        .with_ramp_point("load", {"virtual_dot_0": 0.3},
                        hold_duration=200, ramp_duration=500)
        .with_step_point("measure", {"virtual_dot_0": 0.15}, hold_duration=1000)
        .with_sequence("full_cycle", ["idle", "load", "measure"]))

    # Can also define macros incrementally during calibration
    quantum_dot.with_step_point("readout", {"virtual_dot_0": 0.2}, hold_duration=500)

    # Add to existing sequence
    quantum_dot.with_sequence("extended_cycle",
                             ["idle", "load", "measure", "readout"])


# ============================================================================
# Example 4: Dynamic Method Calling via __getattr__
# ============================================================================

def example_04_method_calling(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Calling macros as methods using __getattr__ magic.

    After defining macros (via any method), they can be called as if they
    were methods decorated with @QuantumComponent.register_macro.

    This provides the same clean API as statically-defined macros while
    maintaining full flexibility for dynamic calibration-time definition.
    """
    # Define macros using fluent API
    (quantum_dot
        .with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)
        .with_ramp_point("load", {"virtual_dot_0": 0.3},
                        hold_duration=200, ramp_duration=500)
        .with_sequence("init", ["idle", "load"]))

    # Call macros as methods (via __getattr__)
    with qua.program() as prog:
        quantum_dot.idle()           # Calls StepPointMacro
        quantum_dot.load()           # Calls RampPointMacro
        quantum_dot.init()           # Calls SequenceMacro

        # With parameter overrides
        quantum_dot.idle(hold_duration=200)
        quantum_dot.load(hold_duration=300, ramp_duration=600)

    # This is equivalent to (but cleaner than):
    with qua.program() as prog:
        quantum_dot.macros["idle"]()
        quantum_dot.macros["load"]()
        quantum_dot.macros["init"]()


# ============================================================================
# Example 5: Complex Calibration Workflow
# ============================================================================

def example_05_calibration_workflow(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Realistic calibration workflow demonstrating dynamic macro definition.

    Shows how macros can be defined, tested, and refined during calibration
    based on measurement results, while maintaining clean calling syntax.
    """
    # Stage 1: Define initial voltage points for calibration
    (quantum_dot
        .with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)
        .with_step_point("load", {"virtual_dot_0": 0.3}, hold_duration=200))

    # Stage 2: Test and measure (simulated)
    with qua.program() as test_prog:
        quantum_dot.idle()
        quantum_dot.load()
        # ... measurement code ...

    # Stage 3: Based on results, add optimized ramp macro
    quantum_dot.with_ramp_point(
        "optimized_load",
        {"virtual_dot_0": 0.32},  # Adjusted voltage from calibration
        hold_duration=180,
        ramp_duration=450
    )

    # Stage 4: Create calibration sequence
    quantum_dot.with_sequence("calibrated_init", ["idle", "optimized_load"])

    # Stage 5: Test new sequence
    with qua.program() as final_prog:
        quantum_dot.calibrated_init()
        # ... proceed with experiment ...

    # Stage 6: Add more complex sequences based on calibration
    quantum_dot.with_step_point("measure_point", {"virtual_dot_0": 0.15},
                               hold_duration=1000)
    quantum_dot.with_sequence("full_protocol",
                             ["calibrated_init", "measure_point"])


# ============================================================================
# Example 6: Parameter Overrides
# ============================================================================

def example_06_parameter_overrides(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Runtime parameter overrides for macro customization.

    All macros support parameter overrides at call time, allowing you to
    reuse the same macro definition with different timing parameters.
    """
    # Define base macros
    (quantum_dot
        .with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)
        .with_ramp_point("load", {"virtual_dot_0": 0.3},
                        hold_duration=200, ramp_duration=500))

    with qua.program() as prog:
        # Use default parameters
        quantum_dot.idle()  # hold_duration=100

        # Override hold duration
        quantum_dot.idle(hold_duration=150)

        # Override both ramp and hold duration
        quantum_dot.load(ramp_duration=600, hold_duration=250)

    # Overrides work with dictionary access too
    quantum_dot.macros["idle"](hold_duration=300)
    quantum_dot.macros["load"](ramp_duration=400)


# ============================================================================
# Example 7: Nested Sequences
# ============================================================================

def example_07_nested_sequences(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Creating nested sequences by composing sequence macros.

    Sequences can reference other sequences, enabling hierarchical
    composition of complex protocols.
    """
    # Define primitive macros
    (quantum_dot
        .with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)
        .with_ramp_point("load", {"virtual_dot_0": 0.3},
                        hold_duration=200, ramp_duration=500)
        .with_step_point("manipulate", {"virtual_dot_0": 0.25}, hold_duration=150)
        .with_step_point("readout", {"virtual_dot_0": 0.15}, hold_duration=1000))

    # Build sub-sequences
    quantum_dot.with_sequence("init", ["idle", "load"])
    quantum_dot.with_sequence("readout_seq", ["manipulate", "readout"])

    # Compose higher-level sequence from sub-sequences
    # Note: You need to store init and readout_seq as macros first
    quantum_dot.with_sequence("full_experiment", ["init", "readout_seq"])

    # Execute nested sequence
    with qua.program() as prog:
        quantum_dot.full_experiment()  # Executes all 4 primitive operations


# ============================================================================
# Example 8: Multi-Dot Coordination
# ============================================================================

def example_08_multi_dot_coordination(
    dot1: VoltagePointMacroMixin,
    dot2: VoltagePointMacroMixin
) -> None:
    """
    Coordinating macros across multiple quantum dots.

    Shows how to define and execute macros on multiple quantum dot components
    simultaneously, useful for two-qubit operations.
    """
    # Define macros for dot 1
    (dot1
        .with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)
        .with_ramp_point("couple", {"virtual_dot_0": 0.25},
                        hold_duration=200, ramp_duration=400))

    # Define macros for dot 2
    (dot2
        .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
        .with_ramp_point("couple", {"virtual_dot_1": 0.22},
                        hold_duration=200, ramp_duration=400))

    # Execute coordinated sequence
    with qua.program() as prog:
        # Initialize both dots
        dot1.idle()
        dot2.idle()

        # Couple them together (could be in parallel in real QUA)
        dot1.couple()
        dot2.couple()

        # Return to idle
        dot1.idle()
        dot2.idle()


# ============================================================================
# Example 9: Replacing and Updating Macros
# ============================================================================

def example_09_updating_macros(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Replacing and updating macro definitions during calibration.

    Shows how to replace existing macros with updated versions based on
    calibration results, maintaining the same macro name.
    """
    # Initial definition
    quantum_dot.with_step_point("load", {"virtual_dot_0": 0.3}, hold_duration=200)

    # Test the macro
    with qua.program() as test1:
        quantum_dot.load()

    # Based on measurements, update the voltage and timing
    quantum_dot.with_step_point(
        "load",
        {"virtual_dot_0": 0.32},  # Updated voltage
        hold_duration=180,         # Updated timing
        replace_existing_point=True
    )

    # Test updated macro (same name, new behavior)
    with qua.program() as test2:
        quantum_dot.load()  # Now uses updated parameters

    # Can also change macro type (step -> ramp)
    quantum_dot.with_ramp_point(
        "load",
        {"virtual_dot_0": 0.32},
        hold_duration=180,
        ramp_duration=500,
        replace_existing_point=True
    )

    # Same call, now uses ramp instead of step
    with qua.program() as test3:
        quantum_dot.load()


# ============================================================================
# Example 10: Serialization and Loading
# ============================================================================

def example_10_serialization(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Serialization compatibility demonstration.

    All macro definitions are fully serializable through QuAM's standard
    serialization mechanism. Macros are stored in the self.macros dict
    and can be saved/loaded with the rest of the QuAM state.
    """
    # Define macros using any method
    (quantum_dot
        .with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)
        .with_ramp_point("load", {"virtual_dot_0": 0.3},
                        hold_duration=200, ramp_duration=500)
        .with_sequence("init", ["idle", "load"]))

    # Macros are in self.macros dict (serializable)
    print("Defined macros:", list(quantum_dot.macros.keys()))
    # Output: ['idle', 'load', 'init']

    # After serialization/deserialization, macros remain callable as methods
    # (Assuming quantum_dot is saved and loaded via QuAM's save/load)

    # The __getattr__ mechanism works immediately after loading
    with qua.program() as prog:
        quantum_dot.idle()  # Works after deserialization
        quantum_dot.load()
        quantum_dot.init()

    # All references are preserved through serialization
    assert "idle" in quantum_dot.macros
    assert "load" in quantum_dot.macros
    assert "init" in quantum_dot.macros


# ============================================================================
# Example 11: Error Handling and Validation
# ============================================================================

def example_11_error_handling(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Proper error handling when working with macros.

    Shows common errors and how to handle them gracefully.
    """
    # Define some macros
    quantum_dot.with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)

    # Error 1: Trying to create sequence with non-existent macro
    try:
        quantum_dot.with_sequence("bad_seq", ["idle", "nonexistent"])
    except KeyError as e:
        print(f"Error: {e}")
        # Output: Cannot create sequence 'bad_seq': macro 'nonexistent' not found

    # Error 2: Accessing undefined macro as method
    try:
        quantum_dot.undefined_macro()
    except AttributeError as e:
        print(f"Error: {e}")
        # Output: 'ExampleQuantumDot' object has no attribute or macro 'undefined_macro'

    # Correct approach: Check if macro exists
    if "idle" in quantum_dot.macros:
        quantum_dot.idle()

    # Error 3: Duplicate point without replace flag
    try:
        quantum_dot.with_step_point("idle", {"virtual_dot_0": 0.2}, hold_duration=150)
    except ValueError as e:
        print(f"Error: {e}")
        # Output: Point 'idle' already exists as 'quantum_dot_0_idle'

    # Correct approach: Use replace flag
    quantum_dot.with_step_point(
        "idle",
        {"virtual_dot_0": 0.2},
        hold_duration=150,
        replace_existing_point=True
    )


# ============================================================================
# Example 12: Complete Real-World Workflow
# ============================================================================

def example_12_complete_workflow(quantum_dot: VoltagePointMacroMixin) -> None:
    """
    Complete real-world workflow from calibration to experiment.

    This example shows a realistic end-to-end workflow:
    1. Define basic voltage points
    2. Create calibration sequences
    3. Run calibration measurements
    4. Refine based on results
    5. Create final experiment sequence
    6. Execute experiment
    """
    # === STAGE 1: Initial Voltage Point Definition ===
    (quantum_dot
        .with_step_point("empty", {"virtual_dot_0": 0.05}, hold_duration=100)
        .with_step_point("load", {"virtual_dot_0": 0.3}, hold_duration=200)
        .with_step_point("manip", {"virtual_dot_0": 0.25}, hold_duration=150)
        .with_step_point("readout", {"virtual_dot_0": 0.15}, hold_duration=1000))

    # === STAGE 2: Create Calibration Sequences ===
    quantum_dot.with_sequence("cal_load", ["empty", "load", "empty"])
    quantum_dot.with_sequence("cal_readout", ["empty", "readout", "empty"])

    # === STAGE 3: Run Calibration (simulated) ===
    with qua.program() as calibration_prog:
        # Calibrate loading
        quantum_dot.cal_load()
        # ... measurement code ...

        # Calibrate readout
        quantum_dot.cal_readout()
        # ... measurement code ...

    # === STAGE 4: Refine Based on Calibration Results ===
    # Suppose calibration showed we need slower loading
    quantum_dot.with_ramp_point(
        "optimized_load",
        {"virtual_dot_0": 0.31},  # Adjusted voltage
        hold_duration=180,
        ramp_duration=600,  # Slower ramp for adiabaticity
    )

    # Add wait time macro if needed
    quantum_dot.with_step_point(
        "wait",
        {"virtual_dot_0": 0.25},
        hold_duration=500
    )

    # === STAGE 5: Create Final Experiment Sequence ===
    quantum_dot.with_sequence(
        "experiment",
        ["empty", "optimized_load", "manip", "wait", "readout", "empty"]
    )

    # === STAGE 6: Run Experiment ===
    with qua.program() as experiment_prog:
        # Simple one-line execution of full protocol
        quantum_dot.experiment()

        # Can still override parameters if needed for specific runs
        quantum_dot.experiment()  # Run 1 with default parameters

        # Or call individual steps for debugging
        quantum_dot.empty()
        quantum_dot.optimized_load(hold_duration=200)  # Override for testing
        quantum_dot.manip()
        quantum_dot.wait(hold_duration=1000)  # Longer wait for this run
        quantum_dot.readout()
        quantum_dot.empty()

    print("Experiment sequence defined and ready!")
    print(f"Available macros: {list(quantum_dot.macros.keys())}")


# ============================================================================
# Summary and Best Practices
# ============================================================================

"""
BEST PRACTICES SUMMARY:

1. **Use Fluent API for New Code**
   - Cleaner syntax with method chaining
   - Automatically handles references and parent linking
   - Example: .with_step_point().with_ramp_point().with_sequence()

2. **Call Macros as Methods**
   - Use dot notation: quantum_dot.idle() instead of quantum_dot.macros["idle"]()
   - Provides @register_macro-like API while maintaining flexibility
   - Works automatically via __getattr__

3. **Define Macros During Calibration**
   - Don't hard-code all macros in class definition
   - Create and refine macros based on measurement results
   - Use replace_existing_point=True to update definitions

4. **Compose Complex Sequences**
   - Build simple primitive macros first
   - Compose them into higher-level sequences
   - Sequences can reference other sequences

5. **Override Parameters When Needed**
   - All macros support runtime parameter overrides
   - Use overrides for testing and optimization
   - Example: quantum_dot.load(hold_duration=300)

6. **Everything is Serializable**
   - All state stored in self.macros dict
   - No special serialization handling needed
   - Macros work immediately after deserialization

7. **Traditional API Still Works**
   - Backward compatible with existing code
   - Use helper methods for gradual migration
   - Full control when needed

MIGRATION GUIDE:

From:
    quantum_dot.add_point("idle", {"virtual_dot_0": 0.1}, duration=100)
    macro = StepPointMacro(point_name="idle", hold_duration=100)
    quantum_dot.macros["idle"] = macro

To:
    quantum_dot.with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)

From:
    quantum_dot.macros["idle"]()

To:
    quantum_dot.idle()
"""


__all__ = [
    "ExampleQuantumDot",
    "example_01_traditional_api",
    "example_02_helper_methods",
    "example_03_fluent_api",
    "example_04_method_calling",
    "example_05_calibration_workflow",
    "example_06_parameter_overrides",
    "example_07_nested_sequences",
    "example_08_multi_dot_coordination",
    "example_09_updating_macros",
    "example_10_serialization",
    "example_11_error_handling",
    "example_12_complete_workflow",
]