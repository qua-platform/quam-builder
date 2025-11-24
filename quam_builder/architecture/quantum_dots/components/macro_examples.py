"""
Essential examples demonstrating voltage point and sequence macro functionality.

This module showcases the 5 most important features of the macro system:

1. **Fluent API**: Modern method chaining for clean macro definition
2. **Dynamic Method Calling**: Call macros as methods via __getattr__
3. **Parameter Overrides**: Runtime customization of macro parameters
4. **Nested Sequences**: Hierarchical composition of complex protocols
5. **Mixed Macros**: Combining pulse macros and point macros in sequences

Key Features:
- Clean, modern API with method chaining
- Flexibility: Define macros dynamically during calibration
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
# Example 1: Fluent API (Recommended)
# ============================================================================

def example_01_fluent_api(quantum_dot: VoltagePointMacroMixin) -> None:
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
# Example 2: Dynamic Method Calling
# ============================================================================

def example_02_method_calling(quantum_dot: VoltagePointMacroMixin) -> None:
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
# Example 3: Parameter Overrides
# ============================================================================

def example_03_parameter_overrides(quantum_dot: VoltagePointMacroMixin) -> None:
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
# Example 4: Nested Sequences
# ============================================================================

def example_04_nested_sequences(quantum_dot: VoltagePointMacroMixin) -> None:
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
    # The init and readout_seq are already stored as macros, so they can be referenced
    quantum_dot.with_sequence("full_experiment", ["init", "readout_seq"])

    # Execute nested sequence
    # Each SequenceMacro uses self.parent to resolve its macro references
    with qua.program() as prog:
        quantum_dot.full_experiment()  # Executes all 4 primitive operations


# ============================================================================
# Example 5: Mixed Pulse and Point Sequence Macros
# ============================================================================

def example_05_mixed_pulse_and_point_sequence(qubit) -> None:
    """
    Combining pulse macros and point macros in a single sequence.

    This example demonstrates a realistic quantum dot experiment workflow where
    you need to coordinate voltage point operations (moving between charge states)
    with microwave pulse operations (rotating qubit state).

    This is particularly relevant for:
    - Loss-DiVincenzo qubits where voltage tunes frequency and pulses drive transitions
    - Experiments requiring precise timing of charge and spin operations
    - Complex sequences like dynamical decoupling with voltage modulation

    Prerequisites:
    - The qubit must inherit from both VoltagePointMacroMixin and have pulse capabilities
    - Example: LDQubit has both voltage_sequence (for points) and xy_channel (for pulses)
    """
    from quam.components.macro.qubit_macros import PulseMacro

    # === STAGE 1: Define Voltage Point Macros ===
    # These control the charge state / detuning of the quantum dot
    (qubit
        .with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)
        .with_ramp_point("sweetspot", {"virtual_dot_0": 0.22},
                        hold_duration=200, ramp_duration=400)
        .with_step_point("readout", {"virtual_dot_0": 0.15}, hold_duration=1000))

    # === STAGE 2: Define Pulse Macros ===
    # These drive microwave transitions (assuming pulses are already added to xy_channel)
    # Note: Pulses must be added first via qubit.add_xy_pulse(name, pulse_obj)

    x180_macro = PulseMacro(pulse="x180")
    qubit.macros["x180"] = x180_macro

    y90_macro = PulseMacro(pulse="y90")
    qubit.macros["y90"] = y90_macro

    x90_macro = PulseMacro(pulse="x90")
    qubit.macros["x90"] = x90_macro

    # === STAGE 3: Create Mixed Sequences ===

    # Simple Rabi sequence: Move to sweetspot, apply X rotation, readout
    qubit.with_sequence("rabi_experiment", ["sweetspot", "x180", "readout"])

    # Ramsey sequence: Move to sweetspot, apply Y90, wait, apply Y90, readout
    qubit.with_sequence("ramsey_sequence", ["sweetspot", "y90", "idle", "y90", "readout"])

    # Complex sequence mixing multiple operations
    qubit.with_sequence(
        "complex_protocol",
        ["idle", "sweetspot", "x90", "idle", "y90", "sweetspot", "x180", "readout"]
    )

    # === STAGE 4: Execute Mixed Sequences ===
    with qua.program() as prog:
        # Execute simple Rabi experiment
        # This will: ramp to sweetspot voltage → play X180 pulse → step to readout voltage
        qubit.rabi_experiment()

        # Execute Ramsey sequence
        # This will: ramp to sweetspot → Y90 pulse → step to idle → Y90 pulse → step to readout
        qubit.ramsey_sequence()

        # Execute complex protocol
        qubit.complex_protocol()

        # Can still override parameters for individual calls
        qubit.rabi_experiment()  # Use default durations
        # Note: pulse macros don't support duration override by default,
        # but point macros do: qubit.sweetspot(hold_duration=300)

    # === STAGE 5: Nested Mixed Sequences ===
    # You can also create sequences that reference other mixed sequences

    # Define a calibration sub-sequence
    qubit.with_sequence("calibrate_pi_pulse", ["sweetspot", "x180", "readout", "idle"])

    # Define a main experiment that uses the calibration
    qubit.with_sequence(
        "full_experiment_with_calibration",
        ["calibrate_pi_pulse", "ramsey_sequence", "calibrate_pi_pulse"]
    )

    with qua.program() as prog:
        qubit.full_experiment_with_calibration()


# ============================================================================
# Summary and Best Practices
# ============================================================================

"""
BEST PRACTICES SUMMARY:

1. **Use Fluent API for New Code**
   - Cleaner syntax with method chaining
   - Automatically handles references and parent linking
   - Example: .with_step_point().with_ramp_point().with_sequence()

2. **Macros Use self.parent Internally**
   - Macros access their component via self.parent (set automatically by QuAM)
   - All apply() methods use self.parent.voltage_sequence, not passed parameters
   - Follows QuAM convention where apply(*args, **kwargs) doesn't receive component

3. **Call Macros as Methods**
   - Use dot notation: quantum_dot.idle() instead of quantum_dot.macros["idle"]()
   - Provides @register_macro-like API while maintaining flexibility
   - Works automatically via __getattr__

4. **Compose Complex Sequences**
   - Build simple primitive macros first
   - Compose them into higher-level sequences
   - Sequences can reference other sequences

5. **Override Parameters When Needed**
   - All macros support runtime parameter overrides
   - Use overrides for testing and optimization
   - Example: quantum_dot.load(hold_duration=300)

6. **Mix Pulse and Point Macros**
   - Both types follow the same apply() interface
   - Can be freely combined in sequence macros
   - SequenceMacro resolves references through self.parent

7. **Everything is Serializable**
   - All state stored in self.macros dict
   - No special serialization handling needed
   - Macros work immediately after deserialization

MIGRATION GUIDE:

From (Old API with point_name):
    quantum_dot.add_point("idle", {"virtual_dot_0": 0.1}, duration=100)
    macro = StepPointMacro(point_name="idle", hold_duration=100)  # Old: used point_name
    quantum_dot.macros["idle"] = macro

To (New API with point_ref):
    # Fluent API (recommended)
    quantum_dot.with_step_point("idle", {"virtual_dot_0": 0.1}, hold_duration=100)

From (Dictionary access):
    quantum_dot.macros["idle"]()

To (Method call):
    quantum_dot.idle()

KEY CHANGES IN NEW SYSTEM:
- Macros use point_ref (reference string) instead of point_name
- apply() methods use self.parent to access component, not passed as parameter
- Parent is set automatically by QuAM when macro is assigned to macros dict
- SequenceMacro.apply() uses self.parent to resolve macro references
"""


__all__ = [
    "ExampleQuantumDot",
    "example_01_fluent_api",
    "example_02_method_calling",
    "example_03_parameter_overrides",
    "example_04_nested_sequences",
    "example_05_mixed_pulse_and_point_sequence",
]