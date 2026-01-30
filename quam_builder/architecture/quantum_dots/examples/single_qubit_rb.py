"""
Single-Qubit Randomized Benchmarking Example for Spin Qubits
=============================================================

This example demonstrates single-qubit randomized benchmarking (RB) for spin qubits.

Experiment Sequence (per RB circuit):
-------------------------------------
1. Initialize: Step to init point, hold for ~400 us
2. Gate Sequence: Apply Clifford gates using native spin qubit operations:
   - X90, X180: Gaussian pulses (physical rotations)
   - Y90, Y180: Gaussian pulses with 90° phase (physical rotations)
   - Z90, Z180, Z270: Virtual Z (frame rotations, zero duration)
3. Measure: Step to measure point, apply RF tone, acquire signal (~400 us)
4. Compensate: Apply 1 ms compensation pulse to reset DC bias

Default Configuration:
---------------------
- Lengths: [2, 4, 8, 16, 32, 64, 96, 128, 160, 192, 224, 256]
- 50 circuits per length
- 400 repetitions (shots) per circuit
- ~400 us init duration
- ~400 us measure duration
- ~500 ns gate duration
- 1 ms compensation pulse

Hardware Requirements:
---------------------
- LF-FEM for voltage gates (plungers, sensors)
- MW-FEM for XY drive (EDSR/ESR)
- Readout resonator for sensor dot RF readout
"""
# ruff: noqa: I001

from dataclasses import dataclass

import numpy as np

from qm import QuantumMachinesManager
from qm.qua import (
    program,
    for_,
    declare,
    declare_stream,
    fixed,
    assign,
    save,
    stream_processing,
    switch_,
    case_,
    align,
    reset_frame,
    frame_rotation_2pi,
    Cast,
    wait,
    Random,
)
from quam.components import pulses
from quam.components.channels import StickyChannelAddon
from quam.components.hardware import FrequencyConverter, LocalOscillator
from quam.components.ports import (
    LFFEMAnalogOutputPort,
    MWFEMAnalogOutputPort,
    LFFEMAnalogInputPort,
)
from quam_builder.architecture.quantum_dots.components import VoltageGate, XYDrive
from quam_builder.architecture.quantum_dots.components.readout_resonator import (
    ReadoutResonatorIQ,
)
from quam_builder.architecture.quantum_dots.examples.html_utils import (
    generate_rb_timing_report,
)
from quam_builder.architecture.quantum_dots.examples.rb_utils import (
    SingleQubitRBResult,
    build_single_qubit_clifford_tables,
    estimate_total_experiment_time,
)
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.qubit import LDQubit


# =============================================================================
# RB Configuration
# =============================================================================


@dataclass
class RBConfig:
    """Configuration for single-qubit RB experiment."""

    circuit_lengths: list[int] | None = None
    num_circuits_per_length: int = 50
    num_shots: int = 400
    gate_duration_ns: int = 500
    init_duration_ns: int = 400_000  # 400 us
    measure_duration_ns: int = 400_000  # 400 us
    compensation_duration_ns: int = 1_000_000  # 1 ms
    rf_readout_duration_ns: int = 10_000  # 10 us
    seed: int = 42

    def __post_init__(self):
        if self.circuit_lengths is None:
            self.circuit_lengths = [2, 4, 8, 16, 32, 64, 96, 128, 160, 192, 224, 256]


# =============================================================================
# Machine Configuration
# =============================================================================


def create_spin_qubit_machine():
    """Create a machine configuration for spin qubit RB.

    Returns:
        Tuple of (machine, xy_drives dict, readout_resonators dict)
    """
    machine = LossDiVincenzoQuam()

    controller = "con1"
    lf_fem_slot = 5
    mw_fem_slot = 1

    # Plunger gates for quantum dots
    plungers = {}
    for i in range(1, 3):
        plungers[i] = VoltageGate(
            id=f"plunger_{i}",
            opx_output=LFFEMAnalogOutputPort(
                controller_id=controller,
                fem_id=lf_fem_slot,
                port_id=i,
                output_mode="direct",
            ),
            sticky=StickyChannelAddon(duration=16, digital=False),
        )

    # Sensor DC channel
    sensor_dc = VoltageGate(
        id="sensor_DC_1",
        opx_output=LFFEMAnalogOutputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=3,
            output_mode="direct",
        ),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

    # Readout resonator for RF readout
    readout_resonator = ReadoutResonatorIQ(
        id="sensor_resonator_1",
        opx_output_I=LFFEMAnalogOutputPort(
            controller_id=controller, fem_id=lf_fem_slot, port_id=4, output_mode="direct"
        ),
        opx_output_Q=LFFEMAnalogOutputPort(
            controller_id=controller, fem_id=lf_fem_slot, port_id=5, output_mode="direct"
        ),
        opx_input_I=LFFEMAnalogInputPort(controller_id=controller, fem_id=lf_fem_slot, port_id=1),
        opx_input_Q=LFFEMAnalogInputPort(controller_id=controller, fem_id=lf_fem_slot, port_id=2),
        frequency_converter_up=FrequencyConverter(
            local_oscillator=LocalOscillator(frequency=200e6),
        ),
        intermediate_frequency=50e6,
        operations={
            "readout": pulses.SquareReadoutPulse(
                length=10000, amplitude=0.1, integration_weights_angle=0.0
            )
        },
    )

    # XY Drive channel
    xy_drives = {}
    xy_drives[1] = XYDrive(
        id="Q1_xy",
        opx_output=MWFEMAnalogOutputPort(
            controller_id=controller,
            fem_id=mw_fem_slot,
            port_id=1,
            upconverter_frequency=5e9,
            band=2,
            full_scale_power_dbm=10,
        ),
        intermediate_frequency=100e6,
        add_default_pulses=True,
    )

    # Add Gaussian pulses for RB gates (~500 ns)
    gate_length = 500
    sigma = gate_length / 6

    xy_drives[1].operations["X90"] = pulses.GaussianPulse(
        length=gate_length, amplitude=0.1, sigma=sigma, axis_angle=0.0
    )
    xy_drives[1].operations["X180"] = pulses.GaussianPulse(
        length=gate_length, amplitude=0.2, sigma=sigma, axis_angle=0.0
    )
    xy_drives[1].operations["Y90"] = pulses.GaussianPulse(
        length=gate_length, amplitude=0.1, sigma=sigma, axis_angle=np.pi / 2
    )
    xy_drives[1].operations["Y180"] = pulses.GaussianPulse(
        length=gate_length, amplitude=0.2, sigma=sigma, axis_angle=np.pi / 2
    )

    # Virtual gate set
    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": plungers[1],
            "virtual_dot_2": plungers[2],
            "virtual_sensor_1": sensor_dc,
        },
        gate_set_id="main_qpu",
        compensation_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    )

    # Register channel elements
    machine.register_channel_elements(
        plunger_channels=list(plungers.values()),
        sensor_resonator_mappings={sensor_dc: readout_resonator},
        barrier_channels=[],
    )

    # Register quantum dot pair
    machine.register_quantum_dot_pair(
        quantum_dot_ids=["virtual_dot_1", "virtual_dot_2"],
        sensor_dot_ids=["virtual_sensor_1"],
        id="qd_pair_1_2",
    )

    # Configure readout threshold
    sensor_dot = machine.sensor_dots["virtual_sensor_1"]
    sensor_dot._add_readout_params(quantum_dot_pair_id="qd_pair_1_2", threshold=0.5)

    return machine, xy_drives, {"1": readout_resonator}


def register_qubit(
    machine: LossDiVincenzoQuam,
    xy_drives: dict,
    rb_config: RBConfig,
) -> LDQubit:
    """Register a qubit with voltage points for RB."""
    machine.register_qubit(
        qubit_name="Q1",
        quantum_dot_id="virtual_dot_1",
        xy_channel=xy_drives[1],
        readout_quantum_dot="virtual_dot_2",
    )

    qubit = machine.qubits["Q1"]

    # Define voltage points
    qubit.add_point_with_step_macro(
        "initialize",
        voltages={"virtual_dot_1": 0.05},
        duration=rb_config.init_duration_ns,
    )
    qubit.add_point(
        "measure",
        voltages={"virtual_dot_1": -0.05},
    )

    return qubit


# =============================================================================
# QUA Program Generation
# =============================================================================


def play_rb_gate(qubit: LDQubit, gate_int):
    """Play a single RB gate on a qubit using switch/case.

    Gate mapping:
        0: X90   - Physical X rotation (pi/2)
        1: X180  - Physical X rotation (pi)
        2: Y90   - Physical Y rotation (pi/2)
        3: Y180  - Physical Y rotation (pi)
        4: Z90   - Virtual Z rotation (pi/2)
        5: Z180  - Virtual Z rotation (pi)
        6: Z270  - Virtual Z rotation (3pi/2)
        7: Idle  - No operation
    """
    xy = qubit.xy_channel

    with switch_(gate_int, unsafe=True):
        with case_(0):  # X90
            xy.play("X90")
        with case_(1):  # X180
            xy.play("X180")
        with case_(2):  # Y90
            xy.play("Y90")
        with case_(3):  # Y180
            xy.play("Y180")
        with case_(4):  # Z90 (virtual)
            frame_rotation_2pi(0.25, xy.name)
        with case_(5):  # Z180 (virtual)
            frame_rotation_2pi(0.5, xy.name)
        with case_(6):  # Z270 (virtual)
            frame_rotation_2pi(0.75, xy.name)
        with case_(7):  # Idle
            xy.wait(4)


def create_rb_qua_program(
    machine: LossDiVincenzoQuam,
    qubit: LDQubit,
    rb_config: RBConfig,
    clifford_tables: dict[str, list[int] | int],
):
    """Create the QUA program for single-qubit RB.

    The program generates Cliffords on the PPU using lookup tables, applies each
    Clifford's native decomposition, and then applies the inverse Clifford to
    return to |0> in the ideal case. This avoids preloading per-circuit gate
    sequences and reduces QUA data memory.
    """
    num_depths = len(rb_config.circuit_lengths)
    num_circuits = rb_config.num_circuits_per_length
    num_cliffords = clifford_tables["num_cliffords"]

    with program() as rb_prog:
        # QUA variables
        n = declare(int)
        n_st = declare_stream()
        depth_idx = declare(int)
        circuit_idx = declare(int)
        gate_idx = declare(int)

        # Lookup tables are precomputed in Python and stored in QUA arrays.
        # They are intentionally compact to minimize data memory usage.
        depths_qua = declare(int, value=rb_config.circuit_lengths)
        clifford_compose_qua = declare(int, value=clifford_tables["compose"])
        clifford_inverse_qua = declare(int, value=clifford_tables["inverse"])
        clifford_decomp_qua = declare(int, value=clifford_tables["decomp_flat"])
        clifford_decomp_offsets_qua = declare(int, value=clifford_tables["decomp_offsets"])
        clifford_decomp_lengths_qua = declare(int, value=clifford_tables["decomp_lengths"])

        current_gate = declare(int)
        current_depth = declare(int)
        total_clifford = declare(int)
        rand_clifford = declare(int)
        inverse_clifford = declare(int)
        decomp_offset = declare(int)
        decomp_length = declare(int)
        clifford_idx = declare(int)

        state = declare(int)
        state_st = declare_stream()

        i_signal = declare(fixed)
        q_signal = declare(fixed)

        # Get sensor and threshold
        sensor_dot = qubit.sensor_dots[0]
        qd_pair_id = machine.find_quantum_dot_pair(
            qubit.quantum_dot.id, qubit.preferred_readout_quantum_dot
        )
        threshold = sensor_dot.readout_thresholds.get(qd_pair_id, 0.0)

        # RNG for on-PPU Clifford generation
        rng = Random()

        # Main experiment loop
        with for_(n, 0, n < rb_config.num_shots, n + 1):
            save(n, n_st)

            with for_(depth_idx, 0, depth_idx < num_depths, depth_idx + 1):
                with for_(circuit_idx, 0, circuit_idx < num_circuits, circuit_idx + 1):
                    assign(current_depth, depths_qua[depth_idx])
                    assign(total_clifford, 0)

                    # --- Initialization ---
                    align()
                    qubit.step_to_point("initialize", duration=rb_config.init_duration_ns)

                    # --- Gate Sequence ---
                    align()
                    with for_(clifford_idx, 0, clifford_idx < current_depth, clifford_idx + 1):
                        assign(rand_clifford, rng.rand_int(num_cliffords))
                        assign(
                            total_clifford,
                            # Composition table is flattened: [left * right].
                            clifford_compose_qua[rand_clifford * num_cliffords + total_clifford],
                        )
                        assign(decomp_offset, clifford_decomp_offsets_qua[rand_clifford])
                        assign(decomp_length, clifford_decomp_lengths_qua[rand_clifford])
                        # Play the native gate decomposition for this Clifford.
                        with for_(gate_idx, 0, gate_idx < decomp_length, gate_idx + 1):
                            assign(current_gate, clifford_decomp_qua[decomp_offset + gate_idx])
                            play_rb_gate(qubit, current_gate)

                    # Apply the inverse Clifford so the ideal sequence returns to |0>.
                    assign(inverse_clifford, clifford_inverse_qua[total_clifford])
                    assign(decomp_offset, clifford_decomp_offsets_qua[inverse_clifford])
                    assign(decomp_length, clifford_decomp_lengths_qua[inverse_clifford])
                    with for_(gate_idx, 0, gate_idx < decomp_length, gate_idx + 1):
                        assign(current_gate, clifford_decomp_qua[decomp_offset + gate_idx])
                        play_rb_gate(qubit, current_gate)

                    reset_frame(qubit.xy_channel.name)

                    # --- Measurement ---
                    align()
                    qubit.step_to_point("measure", duration=rb_config.measure_duration_ns)

                    sensor_dot.readout_resonator.wait(250)  # Settle time
                    sensor_dot.readout_resonator.measure("readout", qua_vars=(i_signal, q_signal))
                    assign(state, Cast.to_int(i_signal > threshold))

                    # --- Compensation ---
                    align()
                    qubit.voltage_sequence.apply_compensation_pulse()
                    wait(rb_config.compensation_duration_ns // 4)

                    # --- Save ---
                    save(state, state_st)

        with stream_processing():
            n_st.save("iteration")
            state_st.buffer(num_circuits).buffer(num_depths).buffer(rb_config.num_shots).save(
                "state"
            )

    return rb_prog


# =============================================================================
# Main Entry Points
# =============================================================================


def setup_rb_experiment(rb_config: RBConfig = None):
    """Set up all components for the single-qubit RB experiment.

    Returns:
        Tuple of (machine, qubit, rb_program, rb_config)
    """
    if rb_config is None:
        rb_config = RBConfig()

    print("Preparing RB lookup tables (PPU-side generation)...")
    clifford_tables = build_single_qubit_clifford_tables()
    total_circuits = len(rb_config.circuit_lengths) * rb_config.num_circuits_per_length
    max_depth = max(rb_config.circuit_lengths)
    max_decomp_length = clifford_tables["max_decomp_length"]
    max_sequence_length = (max_depth + 1) * max_decomp_length

    print(f"  Total circuits: {total_circuits}")
    print(f"  Max sequence length (upper bound): {max_sequence_length} gates")

    time_est = estimate_total_experiment_time(
        rb_config.circuit_lengths,
        rb_config.num_circuits_per_length,
        rb_config.num_shots,
        rb_config.gate_duration_ns,
        rb_config.init_duration_ns / 1000,
        rb_config.measure_duration_ns / 1000,
        rb_config.compensation_duration_ns / 1000,
    )
    print(f"  Estimated experiment time: {time_est['total_time_hours']:.2f} hours")

    print("\nConfiguring machine...")
    machine, xy_drives, _ = create_spin_qubit_machine()
    qubit = register_qubit(machine, xy_drives, rb_config)
    print(f"  Registered qubit: {qubit.id}")

    print("\nCreating QUA program...")
    rb_program = create_rb_qua_program(machine, qubit, rb_config, clifford_tables)

    return machine, qubit, rb_program, rb_config


def analyze_rb_results(results: dict, rb_config: RBConfig) -> SingleQubitRBResult:
    """Analyze RB results and return fidelity metrics."""
    state_data = results["state"]
    state_array = np.array(state_data).reshape(
        len(rb_config.circuit_lengths),
        rb_config.num_circuits_per_length,
        rb_config.num_shots,
    )

    return SingleQubitRBResult(
        circuit_depths=rb_config.circuit_lengths,
        num_circuits_per_length=rb_config.num_circuits_per_length,
        num_averages=rb_config.num_shots,
        state=state_array,
    )


# =============================================================================
# Minimal Wait Program (for latency measurement)
# =============================================================================


def create_minimal_wait_program():
    """Create a minimal QUA program that just waits 16ns.

    Used to measure communication/overhead latency separate from actual program time.
    """
    with program() as wait_prog:
        wait(4)  # 4 cycles = 16ns
    return wait_prog


def calculate_theoretical_time(
    rb_config: RBConfig, average_gates_per_clifford: float = 1.875
) -> dict:
    """Calculate the theoretical minimum execution time for the RB experiment.

    Args:
        rb_config: RB configuration.
        average_gates_per_clifford: Average number of physical gates per Clifford.
            For single-qubit Cliffords with {sx, x, rz}: ~1.875 gates/Clifford.
            Note: Virtual Z gates have zero duration.

    Returns:
        Dictionary with timing breakdown in seconds.
    """
    num_depths = len(rb_config.circuit_lengths)
    num_circuits = rb_config.num_circuits_per_length
    num_shots = rb_config.num_shots
    total_sequences = num_depths * num_circuits * num_shots

    # Time per sequence (in nanoseconds)
    init_ns = rb_config.init_duration_ns
    measure_ns = rb_config.measure_duration_ns
    compensation_ns = rb_config.compensation_duration_ns

    # Average gate time per sequence
    avg_cliffords = np.mean(rb_config.circuit_lengths)
    # Only physical gates take time (X90, X180, Y90, Y180), virtual Z is free
    physical_gates_per_clifford = average_gates_per_clifford * 0.6  # ~60% are physical
    avg_gate_time_ns = avg_cliffords * physical_gates_per_clifford * rb_config.gate_duration_ns

    # Total time per sequence
    time_per_sequence_ns = init_ns + avg_gate_time_ns + measure_ns + compensation_ns
    time_per_sequence_s = time_per_sequence_ns / 1e9

    # Total theoretical time
    total_time_s = total_sequences * time_per_sequence_s

    return {
        "num_depths": num_depths,
        "num_circuits_per_depth": num_circuits,
        "num_shots": num_shots,
        "total_sequences": total_sequences,
        "avg_cliffords": avg_cliffords,
        "init_time_us": init_ns / 1000,
        "measure_time_us": measure_ns / 1000,
        "compensation_time_us": compensation_ns / 1000,
        "avg_gate_time_us": avg_gate_time_ns / 1000,
        "time_per_sequence_us": time_per_sequence_ns / 1000,
        "time_per_sequence_ms": time_per_sequence_ns / 1e6,
        "theoretical_total_s": total_time_s,
    }


def run_timing_benchmark(qm, config, rb_program, wait_program, num_iterations: int = 5):
    """Run both programs multiple times and measure execution times.

    Args:
        qm: Open quantum machine instance.
        config: QUA configuration.
        rb_program: The RB QUA program.
        wait_program: The minimal wait QUA program.
        num_iterations: Number of times to run each program.

    Returns:
        Dictionary with timing results.
    """
    import time

    wait_times = []
    rb_times = []

    print(f"\nRunning timing benchmark ({num_iterations} iterations each)...")

    # Run minimal wait program
    print("  Running minimal wait program...", end=" ", flush=True)
    for _ in range(num_iterations):
        t_start = time.time()
        job = qm.execute(wait_program)
        job.result_handles.wait_for_all_values()
        # job.wait_until("Done")
        wait_times.append(time.time() - t_start)
    print("done")

    # Run RB program
    print("  Running RB program...", end=" ", flush=True)
    for _ in range(num_iterations):
        t_start = time.time()
        job = qm.execute(rb_program)
        job.result_handles.wait_for_all_values()
        # job.wait_until("Done")
        rb_times.append(time.time() - t_start)
    print("done")

    return {
        "wait_times": wait_times,
        "rb_times": rb_times,
        "wait_avg": np.mean(wait_times),
        "wait_std": np.std(wait_times),
        "rb_avg": np.mean(rb_times),
        "rb_std": np.std(rb_times),
        "latency_estimate": np.mean(wait_times),  # Overhead/latency
        "rb_execution_only": np.mean(rb_times) - np.mean(wait_times),  # RB minus overhead
    }


# =============================================================================
# Execution
# =============================================================================


if __name__ == "__main__":
    import time

    # Configuration for real hardware test
    test_config = RBConfig(
        circuit_lengths=[2, 4, 8, 16, 32, 64, 96, 128, 160, 192, 224, 256],
        num_circuits_per_length=50,
        num_shots=400,
        init_duration_ns=400_000,  # 400 us
        measure_duration_ns=400_000,  # 400 us
        compensation_duration_ns=1_000_000,  # 1 ms
        gate_duration_ns=500,  # 500 ns
    )

    print("=" * 60)
    print("Single-Qubit Randomized Benchmarking for Spin Qubits")
    print("=" * 60)

    # Setup
    t_setup_start = time.time()
    machine, qubit, rb_program, rb_config = setup_rb_experiment(test_config)
    setup_time = time.time() - t_setup_start
    print(f"\nSetup completed in {setup_time:.2f} seconds")

    # Create minimal wait program
    wait_program = create_minimal_wait_program()

    # Calculate theoretical time
    theory = calculate_theoretical_time(rb_config)

    print("\n" + "=" * 60)
    print("Theoretical Timing (minimum possible)")
    print("=" * 60)
    print(f"  Circuit depths: {rb_config.circuit_lengths}")
    print(f"  Circuits per depth: {theory['num_circuits_per_depth']}")
    print(f"  Shots per circuit: {theory['num_shots']}")
    print(f"  Total sequences: {theory['total_sequences']:,}")
    print(f"  Average Cliffords: {theory['avg_cliffords']:.1f}")
    print()
    print("  Per sequence breakdown:")
    print(f"    Init:         {theory['init_time_us']:.1f} us")
    print(f"    Gates (avg):  {theory['avg_gate_time_us']:.1f} us")
    print(f"    Measure:      {theory['measure_time_us']:.1f} us")
    print(f"    Compensation: {theory['compensation_time_us']:.1f} us")
    print(f"    Total:        {theory['time_per_sequence_ms']:.3f} ms")
    print()
    print(f"  Theoretical total time: {theory['theoretical_total_s']*1000:.2f} ms")

    # Generate config
    config = machine.generate_config()

    # Connect to real OPX hardware
    print("\n" + "=" * 60)
    print("Connecting to OPX Hardware...")
    print("=" * 60)

    # Uncomment and configure for your hardware:
    from configs import HOST, CLUSTER  # isort:skip

    qmm = QuantumMachinesManager(host=HOST, cluster_name=CLUSTER)

    qm = qmm.open_qm(config)

    # Run timing benchmark
    num_iterations = 3
    timing = run_timing_benchmark(qm, config, rb_program, wait_program, num_iterations)

    print("\n" + "=" * 60)
    print("Measured Timing Results")
    print("=" * 60)
    print("  Minimal wait program (latency estimate):")
    print(f"    Average: {timing['wait_avg']*1000:.2f} ms  (std: {timing['wait_std']*1000:.2f} ms)")
    print(f"    Individual: {[f'{t*1000:.2f}' for t in timing['wait_times']]} ms")
    print()
    print("  RB program:")
    print(f"    Average: {timing['rb_avg']*1000:.2f} ms  (std: {timing['rb_std']*1000:.2f} ms)")
    print(f"    Individual: {[f'{t*1000:.2f}' for t in timing['rb_times']]} ms")
    print()
    print("  Estimated breakdown:")
    print(f"    Communication latency: {timing['latency_estimate']*1000:.2f} ms")
    print(f"    RB execution only:     {timing['rb_execution_only']*1000:.2f} ms")

    print("\n" + "=" * 60)
    print("Comparison: Theoretical vs Measured")
    print("=" * 60)
    print(f"  Theoretical minimum:      {theory['theoretical_total_s']*1000:.2f} ms")
    print(f"  Measured (minus latency): {timing['rb_execution_only']*1000:.2f} ms")
    print(
        f"  Overhead factor:          {timing['rb_execution_only'] / theory['theoretical_total_s']:.2f}x"
    )

    qm.close()

    # Generate HTML report
    print("\n" + "=" * 60)
    print("Generating HTML Report...")
    print("=" * 60)
    report_path = generate_rb_timing_report(rb_config, theory, timing, setup_time)
    print(f"  Report saved to: {report_path}")
