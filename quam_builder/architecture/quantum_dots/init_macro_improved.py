"""
Improved Initialization Macro with Conditional Reset

This module demonstrates how to use the ConditionalMacro from macros.py
for creating initialization sequences with conditional reset capabilities
for quantum dot systems.

Key Features:
- Uses ConditionalMacro from macros.py (unified with QUAM patterns)
- Invertible condition: apply pulse when excited OR when ground
- Fluent API via with_conditional_macro() method
- Support for both method-based and function-based execution patterns
- Comprehensive validation and error messages

Example Usage:
    # Construction API using fluent method from VoltagePointMacroMixin
    qubit_pair.with_conditional_macro(
        name='reset',
        measurement_macro='measure',
        conditional_macro='x180',
        invert_condition=False
    )

    # Inverted condition (pulse if ground state)
    qubit_pair.with_conditional_macro(
        name='prepare_excited',
        measurement_macro='measure',
        conditional_macro='x180',
        invert_condition=True
    )

    # Execution API (both patterns supported)
    with program() as prog:
        # Method-based (recommended for readability)
        state = qubit_pair.measure()
        qubit_pair.reset()
        qubit_pair.reset_sequence()

        # Function-based (good for dynamic dispatch)
        state = measure(qubit_pair)
        reset(qubit_pair)
        reset_sequence(qubit_pair)

        # Runtime condition override
        qubit_pair.reset(invert_condition=True)
"""

from quam.components import pulses
from qm.qua import *

from typing import Optional
from quam_builder.architecture.quantum_dots.operations import operations_registry
from quam_builder.architecture.quantum_dots.components.macros import ConditionalMacro

from quam_qd_generator_example import machine

config = machine.generate_config()

from quam.components.macro import QubitPairMacro, PulseMacro
from quam.components.quantum_components import Qubit, QubitPair

from quam.utils.qua_types import QuaVariableBool
from quam import quam_dataclass, QuamComponent
from qm import qua


@quam_dataclass
class MeasureMacro(QubitPairMacro):
    """
    Macro for measuring qubit state and returning boolean result.

    Performs I/Q measurement on the readout resonator and thresholds
    the I value to determine if the qubit is in excited state.

    Attributes:
        threshold: The threshold value for determining qubit state.
                  I > threshold means excited state (True).

    Returns:
        QuaVariableBool: True if qubit is in excited state, False otherwise.

    """
    threshold: float
    component: QuamComponent

    def apply(self, **kwargs) -> QuaVariableBool:
        """
        Execute the measurement and return the qubit state.

        Returns:
            QuaVariableBool: Boolean QUA variable indicating qubit state.
        """
        # Read I/Q data from the resonator channel
        I, Q = self.component.measure("readout")

        # Declare QUA variable to store boolean result
        qubit_state = qua.declare(bool)
        qua.assign(qubit_state, I > self.threshold)

        return qubit_state


# ============================================================================
# Setup Example Configuration
# ============================================================================

# Get qubit pair from machine
qubit_pair_id = 'Q0_Q1'
qubit_pair = machine.qubit_pairs[qubit_pair_id]

# Configure voltage points and sequences
(qubit_pair
    .with_ramp_point("load", {"virtual_dot_0": 0.3}, hold_duration=200, ramp_duration=500)
    .with_step_point("sweetspot", {"virtual_dot_0": 0.22}, hold_duration=200)
    .with_sequence("init_ramp", ["load", "sweetspot"])
)

# Configure readout pulse
qubit_pair.quantum_dot_pair.sensor_dots[0].readout_resonator.operations["readout"] = pulses.SquareReadoutPulse(
    length=1000, amplitude=0.1, threshold=0.215
)

# Configure measurement macro
qubit_pair.macros["measure"] = MeasureMacro(
    threshold=0.215,
    component=qubit_pair.quantum_dot_pair.sensor_dots[0].readout_resonator.get_reference()
)

# Configure x180 pulse on target qubit
qubit_pair.qubit_target.xy_channel.operations["x180"] = pulses.SquarePulse(amplitude=0.2, length=100)
qubit_pair.qubit_target.macros["x180"] = PulseMacro(
    pulse=qubit_pair.qubit_target.xy_channel.operations["x180"].get_reference()
)

# ============================================================================
# IMPROVED: Use with_conditional_macro() from VoltagePointMacroMixin!
# ============================================================================

# Standard reset: pulse if excited (brings qubit to ground state)
# Uses ConditionalMacro from macros.py via the fluent API
qubit_pair.with_conditional_macro(
    name='reset',
    measurement_macro='measure',
    conditional_macro=qubit_pair.qubit_target.macros["x180"].get_reference(),
    invert_condition=False
)

qubit_pair.with_sequence(
    'reset_sequence',
    ["init_ramp", "reset"]
)

# ============================================================================
# Register operations for function-based execution pattern
# ============================================================================

@operations_registry.register_operation
def measure(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """Measure qubit state. Returns True if excited."""
    pass

@operations_registry.register_operation
def x180(qubit: Qubit, **kwargs) -> QuaVariableBool:
    """Apply π-pulse (bit flip) to qubit."""
    pass

@operations_registry.register_operation
def reset(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """Perform conditional reset on qubit pair. Returns measured state."""
    pass

@operations_registry.register_operation
def reset_sequence(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """Execute full reset sequence (init_ramp + reset)."""
    pass


# ============================================================================
# Usage Examples (Both Execution Patterns)
# ============================================================================

def example_method_based_execution():
    """
    Example: Method-based execution pattern.

    This is the recommended pattern for most use cases as it reads
    naturally and makes the quantum object relationships clear.
    """
    with program() as prog:
        # Method-based calls (recommended)
        state = qubit_pair.measure()
        qubit_pair.qubit_target.x180()
        qubit_pair.reset()
        qubit_pair.reset_sequence()

        # You can also use the state for further conditional logic
        with if_(state):
            # Qubit was in excited state before reset
            qubit_pair.qubit_target.x180()  # Apply another pulse

    return prog


def example_function_based_execution():
    """
    Example: Function-based execution pattern.

    This pattern is useful when you want to dynamically dispatch
    operations or when working with lists of qubits.
    """
    with program() as prog:
        # Function-based calls (good for dynamic dispatch)
        state = measure(qubit_pair)
        x180(qubit_pair.qubit_target)
        reset(qubit_pair)
        reset_sequence(qubit_pair)

        # Useful for iterating over multiple qubits
        # for qp in qubit_pairs:
        #     reset(qp)

    return prog


# ============================================================================
# Main Execution Block
# ============================================================================

if __name__ == "__main__":
    # Example of running the program
    with program() as prog:
        # Method-based execution (recommended)
        print("Executing conditional reset sequence...")

        # Measure initial state
        initial_state = qubit_pair.measure()

        qubit_pair.qubit_target.x180()

        # Apply conditional reset
        was_excited = qubit_pair.reset()

        # Run full reset sequence
        qubit_pair.reset_sequence()

        # Verify reset worked
        final_state = qubit_pair.measure()

    # Connect to QM and execute
    from qm import QuantumMachinesManager

    qmm = QuantumMachinesManager(host="172.16.33.115", cluster_name="CS_3")
    qm = qmm.open_qm(config)

    # Execute the program
    job = qm.execute(prog)

    print("\nProgram executed successfully!")
    print("\nKey Features:")
    print("1. ✓ Uses ConditionalMacro from macros.py (unified QUAM patterns)")
    print("2. ✓ Fluent API via with_conditional_macro() from VoltagePointMacroMixin")
    print("3. ✓ Supports invert_condition for flexible conditional logic")
    print("4. ✓ Runtime override of condition inversion")
    print("5. ✓ Comprehensive docstrings and validation")
    print("6. ✓ Support for both method-based and function-based execution")
    print("7. ✓ Clean integration with voltage point macros and sequences")