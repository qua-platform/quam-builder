"""
Full Multi-Qubit Circuit Implementation

This script implements the full circuit shown in Picture 1.png panel b:
- Initialization: Read Init sequences for qubit pairs (12, 3, 45)
- Operation: Two-qubit exchange gate
- Readout: Final measurements

The circuit structure:
1. Initialize Q1-Q2 with Read Init 12 (×2)
2. Initialize Q3 with Read Init 3
3. Initialize Q4-Q5 with Read Init 45
4. Apply two-qubit exchange operation
5. Readout all qubits
"""

# ============================================================================
# Imports
# ============================================================================
from qm.qua import *
from qm import SimulationConfig
from quam import QuamComponent

from quam.components import pulses
from quam.components.macro import PulseMacro
from quam.components.quantum_components import Qubit, QubitPair
from quam.utils.qua_types import QuaVariableBool
from quam.core import quam_dataclass
from quam.core.macro import QuamMacro

from quam_builder.architecture.quantum_dots.examples.operations import operations_registry
from quam_builder.architecture.quantum_dots.macros import AlignMacro, WaitMacro, MeasureMacro

from quam_qd_generator_example import machine


# ============================================================================
# Configuration Parameters
# ============================================================================

# Configuration for Q1-Q2 pair (Read Init 12)
CONFIG_Q1_Q2 = {
    "voltage_points": {
        "measure_point": {
            "virtual_dot_0": -0.12,
            "virtual_dot_1": -0.12,
            "virtual_barrier_1": -0.0,
        },
        "load_point": {"virtual_dot_0": 0.12, "virtual_dot_1": 0.12, "virtual_barrier_1": 0.0},
        "exchange_point": {
            "virtual_dot_0": 0.12,
            "virtual_dot_1": 0.12,
            "virtual_barrier_1": 0.9,  # High barrier for exchange
        },
    },
    "readout": {"length": 240, "amplitude": 0.12},
    "x180": {"amplitude": 0.25, "length": 120},
    "timing": {"duration": 100, "wait_duration": 240},
    "threshold": 0.05,
}

# Configuration for Q2-Q3 pair (Read Init 3)
CONFIG_Q2_Q3 = {
    "voltage_points": {
        "measure_point": {
            "virtual_dot_0": -0.12,
            "virtual_dot_1": -0.12,
            "virtual_barrier_1": -0.0,
        },
        "load_point": {"virtual_dot_0": 0.12, "virtual_dot_1": 0.12, "virtual_barrier_1": 0.0},
        "exchange_point": {"virtual_dot_0": 0.12, "virtual_dot_1": 0.12, "virtual_barrier_1": 0.95},
    },
    "readout": {"length": 240, "amplitude": 0.12},
    "x180": {"amplitude": 0.25, "length": 120},
    "timing": {"duration": 100, "wait_duration": 240},
    "threshold": 0.05,
}

# Exchange gate timing parameters
EXCHANGE_PARAMS = {
    "ramp_duration": 50,  # Time to ramp barrier up (ns)
    "exchange_duration": 300,  # Time at high barrier (ns)
}


# ============================================================================
# Register Operations
# ============================================================================


@operations_registry.register_operation
def measure(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """Measure qubit state."""
    pass


@operations_registry.register_operation
def x180(qubit: Qubit, **kwargs):
    """Apply π-pulse (bit flip)."""
    pass


@operations_registry.register_operation
def reset(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """Perform conditional reset."""
    pass


@operations_registry.register_operation
def init_sequence(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """Execute full initialization sequence."""
    pass


@operations_registry.register_operation
def measure_init(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """Execute measure and return to load point."""
    pass


@operations_registry.register_operation
def exchange(qubit_pair: QubitPair, **kwargs):
    """Execute two-qubit exchange gate."""
    pass


@operations_registry.register_operation
def full_circuit(qubit_pair: QubitPair, **kwargs):
    """Execute full circuit: init + operation + readout."""
    pass


@operations_registry.register_operation
def psb(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    """PSB (Pauli Spin Blockade) measurement."""
    pass


@operations_registry.register_operation
def init3(qubit_pair: QubitPair, **kwargs) -> QuaVariableBool:
    pass


@operations_registry.register_operation
def correlated_init(
    psb_pair: QubitPair, individual_qubit: Qubit, exchange_pair: QubitPair, **kwargs
) -> QuaVariableBool:
    """
    Generalized correlated initialization sequence.

    Performs:
    1. Exchange gate on exchange_pair
    2. PSB measurement on psb_pair
    3. Conditional X180 on individual_qubit based on PSB result

    Args:
        psb_pair: The qubit pair for PSB measurement
        individual_qubit: The individual qubit for conditional X180
        exchange_pair: The qubit pair containing both qubits for exchange gate
        **kwargs: Additional parameters

    Returns:
        PSB measurement result
    """
    pass


# ============================================================================
# Configuration Helper Functions
# ============================================================================


@quam_dataclass
class CorrelatedInitMacro(QuamMacro):
    """Runtime-created correlated init macro."""

    invert: bool = False

    def apply(
        self,
        exchange_pair: QuamComponent = None,
        psb_pair: QuamComponent = None,
        target_qubit: QuamComponent = None,
        **kwargs,
    ):
        # Step 1: Exchange
        exchange_pair.exchange()
        qua.align()

        # Step 2: PSB
        state = psb_pair.psb()
        qua.align()

        # Step 3: Conditional X180
        condition = ~state if self.invert else state
        with qua.if_(condition):
            target_qubit.x180()
        qua.align()

        return state


def configure_qubit_pair_for_reset(qubit_pair, config):
    """
    Configure a qubit pair with voltage points, readout, and conditional reset.
    Same as init_macro_improved.py but with exchange point added.
    """
    # Extract parameters from config dictionary
    voltage_points = config["voltage_points"]
    readout_params = config["readout"]
    x180_params = config["x180"]
    measure_threshold = config["threshold"]
    duration = config["timing"]["duration"]
    wait_duration = config["timing"]["wait_duration"]

    # Add Voltage Points
    for point_name, voltages in voltage_points.items():
        qubit_pair.add_point(point_name, voltages)

    # Configure Macros and Operations
    qubit_pair.macros["align"] = AlignMacro()
    qubit_pair.macros["wait"] = WaitMacro(duration=wait_duration)

    # Readout system configuration
    qubit_pair.resonator = qubit_pair.quantum_dot_pair.sensor_dots[
        0
    ].readout_resonator.get_reference()
    qubit_pair.resonator.operations["readout"] = pulses.SquareReadoutPulse(**readout_params)
    qubit_pair.macros["measure"] = MeasureMacro(
        threshold=measure_threshold, component=qubit_pair.resonator.get_reference()
    )

    # X180 pulse configuration
    qubit_pair.qubit_target.xy_channel.operations["x180"] = pulses.SquarePulse(**x180_params)
    qubit_pair.qubit_target.macros["x180"] = PulseMacro(
        pulse=qubit_pair.qubit_target.xy_channel.operations["x180"].get_reference()
    )

    # Build Complete Configuration Using Fluent API Chain
    return (
        qubit_pair
        # Configure step points
        .with_step_point("measure_point", duration=duration)
        .with_step_point("load_point", duration=duration)
        .with_ramp_point(
            "exchange_point", duration=16, ramp_duration=EXCHANGE_PARAMS["exchange_duration"]
        )
        # PSB (Pauli Spin Blockade) measurement - just measure at measurement point
        .with_sequence(
            "psb",
            ["measure_point", "align", "measure", "align", "load_point", "align"],
            return_index=2,
        )
        # Measure-and-return-to-load sequence
        .with_sequence(
            "measure_init",
            ["measure_point", "align", "measure", "align", "load_point", "align"],
            return_index=2,
        )
        # Conditional reset macro
        .with_conditional_macro(
            name="reset",
            measurement_macro="measure_init",
            conditional_macro=qubit_pair.qubit_target.macros["x180"].get_reference(),
            invert_condition=False,
        )
        # Full initialization sequence
        .with_sequence(
            "init_sequence", ["reset", "align", "wait", "align", "measure_init"], return_index=-1
        )
        # Exchange gate sequence (ramp to exchange point and back)
        .with_sequence("exchange", ["exchange_point", "align", "load_point", "align"])
        # Full circuit: init + exchange + readout
        .with_sequence(
            "full_circuit",
            ["init_sequence", "align", "exchange", "align", "measure_init"],
            return_index=-1,
        )
    )


# ============================================================================
# Setup All Qubit Pairs
# ============================================================================

# Get qubit pairs
q1 = machine.qubits[f"Q{0}"]
q2 = machine.qubits[f"Q{1}"]
q3 = machine.qubits[f"Q{2}"]


qp_12 = machine.qubit_pairs[f"{q1.id}_{q2.id}"]  # Represents Q1-Q2
qp_23 = machine.qubit_pairs[f"{q2.id}_{q3.id}"]

# Configure each qubit pair with their specific settings
configure_qubit_pair_for_reset(qp_12, config=CONFIG_Q1_Q2)
configure_qubit_pair_for_reset(qp_23, config=CONFIG_Q2_Q3)

# Create the correlated_init macro for Read Init 3 sequence
# This sequence involves Q1-Q2 (PSB), Q3 (conditional X180), and Q2-Q3 (exchange)
# Create and add the macro (don't call it yet - that happens in the QUA program)
machine.qpu.macros["init3"] = CorrelatedInitMacro()

# ============================================================================
# Generate QM Configuration
# ============================================================================
config = machine.generate_config()


# ============================================================================
# Main Execution - Full Circuit Implementation
# ============================================================================
if __name__ == "__main__":
    from qm import qua
    from qm import QuantumMachinesManager
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.use("TkAgg")
    # -----------------------------------------------------------------------
    # Define Full Circuit QUA Program
    # -----------------------------------------------------------------------
    with program() as prog:
        # Declare streams for saving results
        state_12_st = declare_stream()
        state_23_st = declare_stream()
        state_45_st = declare_stream()

        print("Executing full multi-qubit circuit...")

        # ===================================================================
        # INITIALIZATION PHASE
        # ===================================================================
        # Read Init 12 - First initialization of Q1-Q2
        state_12_init = init_sequence(qp_12)
        qua.align()
        # 2× loop: Read Init 3 → Read Init 12
        with for_(n := declare(int), 0, n < 2, n + 1):
            # ---------------------------------------------------------------
            # Read Init 3: Correlated initialization of Q1, Q2, Q3
            # Uses the init3 macro stored in machine.qpu
            # ---------------------------------------------------------------
            state_12_psb = machine.qpu.init3(exchange_pair=qp_23, psb_pair=qp_12, target_qubit=q3)
            qua.align()

            # ---------------------------------------------------------------
            # Read Init 12 - Re-initialize Q1-Q2
            # ---------------------------------------------------------------
            state_12_reinit = init_sequence(qp_12)
            qua.align()

        # Read Init 45 - Initialize Q4-Q5
        # state_45_init = init_sequence(qp_45)
        # qua.align()

        # ===================================================================
        # OPERATION PHASE - Two-Qubit Exchange Gate
        # ===================================================================
        # Apply exchange operation between qubits (Q2-Q3)
        # exchange(qp_23)
        # qua.align()

        # ===================================================================
        # READOUT PHASE
        # ===================================================================
        # Read Init 12 - Final readout of Q1-Q2
        # state_12_final = measure_init(qp_12)
        # qua.align()
        #
        # # Read Init 3 - Final readout of Q2-Q3
        # state_23_final = measure_init(qp_23)
        # qua.align()

        # Read Init 45 - Final readout of Q4-Q5
        # state_45_final = measure_init(qp_45)
        # qua.align()

        # ===================================================================
        # CLEANUP
        # ===================================================================
        qua.wait(100)

        # Ramp all voltages to zero
        qp_12.voltage_sequence.ramp_to_zero()
        qp_23.voltage_sequence.ramp_to_zero()
        # qp_45.voltage_sequence.ramp_to_zero()

        # Save results to streams
        # save(state_12_final, state_12_st)
        # save(state_23_final, state_23_st)
        # save(state_45_final, state_45_st)

        # # Stream processing
        # with stream_processing():
        #     state_12_st.save("state_q12")
        #     state_23_st.save("state_q23")
        # state_45_st.save("state_q45")

    # -----------------------------------------------------------------------
    # Execute Circuit
    # -----------------------------------------------------------------------
    qmm = QuantumMachinesManager(host="172.16.33.114", cluster_name="CS_4")
    qm = qmm.open_qm(config)

    qmm.clear_all_job_results()

    # Run simulation (longer duration for full circuit)
    simulation_config = SimulationConfig(duration=2000)
    job = qmm.simulate(config, prog, simulation_config)

    # Plot results
    job.get_simulated_samples().con1.plot()
    plt.title("Full Multi-Qubit Circuit: Init → Exchange → Readout")
    plt.show()

    # Print results
    # res = job.result_handles
    # out = res.fetch_results()
    # print(f'\nCircuit Results:')
    # print(f'  Q1-Q2 final state: {out.get("state_q12", "N/A")}')
    # print(f'  Q2-Q3 final state: {out.get("state_q23", "N/A")}')
    # print(f'  Q4-Q5 final state: {out.get("state_q45", "N/A")}')

    # -----------------------------------------------------------------------
    # Hardware Execution (commented out)
    # -----------------------------------------------------------------------
    # job = qm.execute(prog)
    # print(job.get_status())
