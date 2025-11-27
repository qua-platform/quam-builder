"""
Improved Initialization Macro with Conditional Reset

This module demonstrates how to use the ConditionalMacro from macros.py
for creating initialization sequences with conditional reset capabilities
for quantum dot systems.

Key Features:
- Uses ConditionalMacro from macros.py (unified with QUAM patterns)
- Invertible condition: apply pulse when excited OR when ground
- Optional element alignment between measurement and conditional operations
- Fluent API via with_conditional_macro() method
- Support for both method-based and function-based execution patterns
- Comprehensive validation and error messages

Example Usage:
    # Construction API using fluent method from VoltagePointMacroMixin
    qubit_pair.with_conditional_macro(
        name='reset',
        measurement_macro='measure',
        conditional_macro='x180',
        invert_condition=False,
        align_elements=['resonator_element', 'xy_element']  # Optional alignment
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

        # Runtime overrides
        qubit_pair.reset(invert_condition=True)
        qubit_pair.reset(align_elements=['element1', 'element2'])
"""
from quam import QuamComponent
from quam.components import pulses
from qm.qua import *
from quam.core.macro import QuamMacro

from typing import Optional
from quam_builder.architecture.quantum_dots.operations import operations_registry
from quam_builder.architecture.quantum_dots.components.macros import ConditionalMacro, AlignMacro, WaitMacro
from qm import SimulationConfig

from quam_qd_generator_example import machine

from quam.components.macro import QubitPairMacro, PulseMacro
from quam.components.quantum_components import Qubit, QubitPair
from quam_builder.architecture.quantum_dots.components.macros import MeasureMacro
from quam.utils.qua_types import QuaVariableBool
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
def init_sequence(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """Execute full reset sequence (init_ramp + reset)."""
    pass


# ============================================================================
# Setup Example Configuration
# ============================================================================
# Get qubit pair from machine
qubit_pair_id = 'Q0_Q1'
qubit_pair = machine.qubit_pairs[qubit_pair_id]

# Configure voltage points and sequences
qubit_pair.add_point(
    "measure_point",
    {"virtual_dot_0": -0.3, "virtual_dot_1": -0.5, "virtual_barrier_1":-0.4}
)
qubit_pair.add_point(
    "load_point",
    {"virtual_dot_0": 0.3, "virtual_dot_1": 0.5, "virtual_barrier_1":0.4}
)
qubit_pair.add_point(
    "operate",
    {"virtual_dot_0": 0.6, "virtual_dot_1": 0.8, "virtual_barrier_1":0.8}
)

(qubit_pair
    .with_step_point("measure_point", hold_duration=100) #, ramp_duration=100)
    .with_step_point("load_point", hold_duration=100) #, ramp_duration=100)
)
qubit_pair.macros["align"] = AlignMacro()

# Configure readout pulse
qubit_pair.resonator = qubit_pair.quantum_dot_pair.sensor_dots[0].readout_resonator.get_reference()

qubit_pair.resonator.operations["readout"] = pulses.SquareReadoutPulse(
    length=100, amplitude=0.1
)

# Configure measurement macro
qubit_pair.macros["measure"] = MeasureMacro(
    threshold=0.,
    component=qubit_pair.resonator.get_reference()
)

qubit_pair.with_sequence(
    'measure_init',
    ['measure_point', "align", 'measure', 'align', 'load_point', 'align'],
    return_index=2
)

# Configure x180 pulse on target qubit
qubit_pair.qubit_target.xy_channel.operations["x180"] = pulses.SquarePulse(amplitude=0.2, length=100)
qubit_pair.qubit_target.macros["x180"] = PulseMacro(
    pulse=qubit_pair.qubit_target.xy_channel.operations["x180"].get_reference()
)
qubit_pair.macros['target_x180'] = qubit_pair.qubit_target.macros["x180"].get_reference()

qubit_pair.with_conditional_macro(
    name='reset',
    measurement_macro='measure_init',
    conditional_macro=qubit_pair.qubit_target.macros["x180"].get_reference(), # need referencing as this is not in the namespace of the qubit_pair macros
    invert_condition=True
)

qubit_pair.with_sequence(
    'psb',
    ['measure_point', "align", 'measure'],
)

qubit_pair.macros['long_wait'] = WaitMacro(duration=200)
qubit_pair.with_sequence(
    'init_sequence',
    ["load_point", 'align', 'reset', 'align', 'long_wait', 'align', 'measure_init'],
    return_index=-1
)

# qubit_pair.with_sequence(
#     'init_sequence',
#     ["measure"],
#     return_index=0
# )

# ======================================================================
# Generate config AFTER all operations are configured
# ============================================================================
config = machine.generate_config()


# ============================================================================
# Main Execution Block
# ============================================================================
from qm import qua
if __name__ == "__main__":
    # Example of running the program
    with program() as prog:
        n_st = declare_stream()  # Stream for the averaging iteration 'n'
        # with infinite_loop_():
        print("Executing conditional reset sequence...")
        # Run full reset sequence
        # state = measure(qubit_pair)
        # state = qubit_pair.reset()

        # Run full reset sequence
        state = init_sequence(qubit_pair)

        qua.align()
        qua.wait(100)

        qubit_pair.voltage_sequence.ramp_to_zero()

        save(state, n_st)

        with stream_processing():
            n_st.save("state")

        # Apply compensation and zero voltages
        # qubit_pair.voltage_sequence.apply_compensation_pulse()

    # Connect to QM and execute
    from qm import QuantumMachinesManager
    qmm = QuantumMachinesManager(host="172.16.33.114", cluster_name="CS_4")
    qm = qmm.open_qm(config)

    import matplotlib
    import matplotlib.pyplot as plt
    matplotlib.use('TkAgg')

    qmm.clear_all_job_results()
    # simulate
    simulation_config = SimulationConfig(duration=800)  # in clock cycles
    job = qmm.simulate(config, prog, simulation_config)
    job.get_simulated_samples().con1.plot()
    plt.show()
    # # Execute the program
    # job = qm.execute(prog)
    #
    # print(job.get_status())

    res = job.result_handles
    out = res.fetch_results()
    print(f'results = {out}')
