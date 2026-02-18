"""
# pylint: disable=duplicate-code,wrong-import-order,import-outside-toplevel,ungrouped-imports,consider-using-with,too-many-lines,too-many-branches

Improved Initialization Macro with Conditional Reset

This module demonstrates how to use the ConditionalMacro from point_macros.py
for creating initialization sequences with conditional reset capabilities
for quantum dot systems.

Key Features:
- Uses ConditionalMacro from point_macros.py (unified with QUAM patterns)
- Invertible condition: apply pulse when excited OR when ground
- Fluent API via with_conditional_macro() method
- Support for both method-based and function-based execution patterns
- Configuration-driven setup for easy customization

Example Usage:
    # Construction API using fluent method from VoltageMacroMixin
    qubit_pair.with_conditional_macro(
        name='reset',
        measurement_macro='measure',
        conditional_macro='x180',
        invert_condition=False,
    )

    # Execution API (both patterns supported)
    with program() as prog:
        # Method-based (recommended for readability)
        state = qubit_pair.measure()
        qubit_pair.reset()

        # Function-based (good for dynamic dispatch)
        state = measure(qubit_pair)
        reset(qubit_pair)
        init_sequence(qubit_pair)
"""

# ============================================================================
# Imports
# ============================================================================
from qm.qua import *

from quam.components import pulses
from quam.components.macro import PulseMacro
from quam.components.quantum_components import Qubit, QubitPair
from quam.utils.qua_types import QuaVariableBool

from quam_builder.architecture.quantum_dots.operations import operations_registry
from quam_builder.tools.macros import MeasureMacro

from quam_qd_generator_example import machine

# ============================================================================
# Register Operations for Function-Based Execution Pattern
# ============================================================================
# These decorators register operations that can be called as functions.
# The 'pass' statements are intentional - the decorator handles dispatching
# to the actual macro implementations on the quantum components.


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
def init_sequence(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """Execute full initialization sequence (reset + wait + measure)."""
    pass


@operations_registry.register_operation
def measure_init(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """Execute measure and return to load point."""
    pass


# ============================================================================
# Configuration Helper Function
# ============================================================================


def configure_qubit_pair_for_reset(qubit_pair, config):
    """
    Configure a qubit pair with voltage points, readout, and conditional reset.

    Args:
        qubit_pair: QubitPair instance to configure
        config: Configuration dictionary with structure:
            {
                "voltage_points": {
                    "measure_point": {"virtual_dot_0": ..., "virtual_dot_1": ..., ...},
                    "load_point": {...},
                    "operate": {...}
                },
                "readout": {"length": ..., "amplitude": ...},
                "x180": {"amplitude": ..., "length": ...},
                "timing": {"duration": ..., "wait_duration": ...},
                "threshold": ...
            }
            If None, uses DEFAULT_RESET_CONFIG

    Returns:
        Configured qubit_pair for method chaining
    """

    # Extract parameters from config dictionary
    voltage_points = config["voltage_points"]
    readout_params = config["readout"]
    x180_params = config["x180"]
    measure_threshold = config["threshold"]
    duration = config["timing"]["duration"]
    wait_duration = config["timing"]["wait_duration"]

    # ----------------------------------------------------------------------------
    # Add Voltage Points (non-fluent operation)
    # ----------------------------------------------------------------------------
    for point_name, voltages in voltage_points.items():
        qubit_pair.add_point(point_name, voltages)

    # ----------------------------------------------------------------------------
    # Configure Macros and Operations (non-fluent assignments)
    # ----------------------------------------------------------------------------

    # Readout system configuration
    qubit_pair.resonator = qubit_pair.quantum_dot_pair.sensor_dots[
        0
    ].readout_resonator.get_reference()
    qubit_pair.resonator.operations["readout"] = pulses.SquareReadoutPulse(**readout_params)
    qubit_pair.macros["measure"] = MeasureMacro(
        threshold=measure_threshold, component=qubit_pair.resonator.get_reference()
    )

    # X180 pulse configuration for conditional reset
    qubit_pair.qubit_target.xy_channel.operations["x180"] = pulses.SquarePulse(**x180_params)
    qubit_pair.qubit_target.macros["x180"] = PulseMacro(
        pulse=qubit_pair.qubit_target.xy_channel.operations["x180"].get_reference()
    )

    # ----------------------------------------------------------------------------
    # Build Complete Configuration Using Fluent API Chain
    # ----------------------------------------------------------------------------
    (
        qubit_pair
        # Configure step points with hold durations
        .with_step_point("measure_point", duration=duration).with_step_point(
            "load_point", duration=duration
        )
        # Create measure-and-return-to-load sequence
        .with_sequence(
            "measure_init",
            ["measure_point", "measure", "load_point"],
            return_index=2,  # Return measurement result
        )
        # Create conditional reset macro (measure + conditional X180)
        .with_conditional_macro(
            name="reset",
            measurement_macro="measure_init",
            conditional_macro=qubit_pair.qubit_target.macros["x180"].get_reference(),
            invert_condition=False,  # Apply X180 when in ground state
        )
        # Create full initialization sequence (reset + wait + measure)
        .with_sequence(
            "init_sequence",
            ["reset", "measure_init"],
            return_index=-1,  # Return final measurement result
        )
    )


# ============================================================================
# Setup Quantum Dot Configuration
# ============================================================================

# Configure all qubit pairs with default configuration
custom_config = {
    "voltage_points": {
        "measure_point": {"virtual_dot_0": -0.4, "virtual_dot_1": -0.6, "virtual_barrier_1": -0.5},
        "load_point": {"virtual_dot_0": 0.3, "virtual_dot_1": 0.5, "virtual_barrier_1": 0.4},
        "operate": {"virtual_dot_0": 0.6, "virtual_dot_1": 0.8, "virtual_barrier_1": 0.8},
    },
    "readout": {"length": 240, "amplitude": 0.12},
    "x180": {"amplitude": 0.25, "length": 120},
    "timing": {"duration": 100, "wait_duration": 240},
    "threshold": 0.05,
}

for qubit_pair in machine.qubit_pairs.values():
    configure_qubit_pair_for_reset(qubit_pair, config=custom_config)

# ============================================================================
# Generate QM Configuration
# ============================================================================
# IMPORTANT: Config generation must happen AFTER all operations are defined
config = machine.generate_config()


# ============================================================================
# Main Execution Block
# ============================================================================
if __name__ == "__main__":
    from qm import qua
    import matplotlib

    # Configure matplotlib for interactive plotting
    matplotlib.use("TkAgg")

    # -----------------------------------------------------------------------
    # Define QUA Program
    # -----------------------------------------------------------------------
    with program() as prog:
        # Declare stream for saving measurement results
        n_st = declare_stream()

        print("Executing conditional reset sequence...")

        # Execute initialization sequence on all qubit pairs
        for qp_id, qubit_pair in machine.qubit_pairs.items():
            # Option 1: function based
            state = init_sequence(qubit_pair)
            # Option 2: method based
            # state = qubit_pair.init_sequence()

        qua.wait(100)

        # Ramp all voltages back to zero at end of sequence
        qubit_pair.voltage_sequence.ramp_to_zero()

        # Save the measurement result to stream
        save(state, n_st)

        # Configure stream processing to save data
        with stream_processing():
            n_st.save("state")

    # -----------------------------------------------------------------------
    # Connect to Quantum Machines and Execute
    # -----------------------------------------------------------------------

    # # Connect to the OPX controller
    # qmm = QuantumMachinesManager(host="172.16.33.114", cluster_name="CS_4")
    # qm = qmm.open_qm(config)
    #
    # # Clear previous job results
    # qmm.clear_all_job_results()
    #
    # # Run simulation (800 clock cycles = 3200ns with 4ns clock period)
    # simulation_config = SimulationConfig(duration=800)
    # job = qmm.simulate(config, prog, simulation_config)
    #
    # # Plot simulated waveforms
    # job.get_simulated_samples().con1.plot()
    # plt.show()
    #
    # # Retrieve and print results
    # res = job.result_handles
    # out = res.fetch_results()
    # print(f'Results: {out}')

    # -----------------------------------------------------------------------
    # Hardware Execution (commented out - uncomment to run on real hardware)
    # -----------------------------------------------------------------------
    # job = qm.execute(prog)
    # print(job.get_status())
