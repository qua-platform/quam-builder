"""
Single-Qubit Randomized Benchmarking Example for Spin Qubits
=============================================================

This example demonstrates single-qubit randomized benchmarking (RB) for spin qubits.
It shows how to:

1. Configure a minimal quantum dot machine with virtual gates
2. Define voltage points for init, operate, and measure
3. Create custom macros for init/measure with ramps and RF readout
4. Generate RB circuits using Qiskit's Clifford library
5. Build a QUA program for single-qubit RB

Experiment Sequence (per RB circuit):
-------------------------------------
1. Initialize: Ramp to init point, hold for ~400 us
2. Gate Sequence: Apply Clifford gates (Gaussian pulses for X90/Y90/X180/Y180,
   virtual Z for frame rotations). Each gate ~500 ns.
3. Measure: Ramp to measure point, apply RF tone, acquire signal (~400 us)
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

Timing is measured at the Python level for the entire program execution.

Hardware Requirements:
---------------------
- LF-FEM for voltage gates (plungers, sensors)
- MW-FEM for XY drive (EDSR/ESR)
- Readout resonator for sensor dot RF readout
"""

from typing import List, Dict
from dataclasses import dataclass

import numpy as np
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
)
from qm import SimulationConfig, QuantumMachinesManager
import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from quam.components import pulses
from quam.components.ports import (
    LFFEMAnalogOutputPort,
    MWFEMAnalogOutputPort,
    LFFEMAnalogInputPort,
)
from quam.components.channels import StickyChannelAddon
from quam.components.hardware import FrequencyConverter, LocalOscillator
from quam.core import quam_dataclass
from quam.core.macro.quam_macro import QuamMacro

from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    XYDrive,
)
from quam_builder.architecture.quantum_dots.components.readout_resonator import (
    ReadoutResonatorIQ,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit

# Import RB utilities
from quam_builder.architecture.quantum_dots.examples.rb_utils import (
    SingleQubitStandardRB,
    SingleQubitRBResult,
    process_circuit_to_integers,
    prepare_circuits_for_qua,
    estimate_total_experiment_time,
    SINGLE_QUBIT_GATE_MAP,
)


# =============================================================================
# SECTION 1: RB Configuration
# =============================================================================


@dataclass
class RBConfig:
    """Configuration for single-qubit RB experiment.

    Attributes:
        circuit_lengths: List of Clifford depths to benchmark.
        num_circuits_per_length: Number of random circuits per depth.
        num_shots: Number of repetitions (averages) per circuit.
        gate_duration_ns: Duration of Gaussian gates in nanoseconds.
        init_duration_ns: Initialization ramp + hold duration in nanoseconds.
        measure_duration_ns: Measurement duration in nanoseconds.
        compensation_duration_ns: Compensation pulse duration in nanoseconds.
        rf_readout_duration_ns: RF tone duration for readout.
        seed: Random seed for reproducibility.
    """

    circuit_lengths: List[int] = None
    num_circuits_per_length: int = 50
    num_shots: int = 400
    gate_duration_ns: int = 500  # ~500 ns Gaussian pulses
    init_duration_ns: int = 400_000  # 400 us
    measure_duration_ns: int = 400_000  # 400 us (includes RF readout)
    compensation_duration_ns: int = 1_000_000  # 1 ms
    rf_readout_duration_ns: int = 10_000  # 10 us RF tone
    ramp_duration_ns: int = 1000  # 1 us ramps for init/measure transitions
    seed: int = 42

    def __post_init__(self):
        if self.circuit_lengths is None:
            self.circuit_lengths = [2, 4, 8, 16, 32, 64, 96, 128, 160, 192, 224, 256]


# =============================================================================
# SECTION 2: Custom Macros for Spin Qubit RB
# =============================================================================


@quam_dataclass
class InitMacro(QuamMacro):
    """Macro for initialization: ramp to init point and hold.

    This macro:
    1. Ramps to the 'initialize' voltage point
    2. Holds for the specified duration to allow electron loading

    Attributes:
        ramp_duration: Duration of voltage ramp in ns.
        hold_duration: Duration to hold at init point in ns.
    """

    ramp_duration: int = 1000
    hold_duration: int = 800_000

    def apply(self, hold_duration: int = None, ramp_duration: int = None, **kwargs):
        """Execute initialization sequence.

        Args:
            hold_duration: Optional override for hold duration.
            ramp_duration: Optional override for ramp duration.
        """
        parent_qubit = self.parent.parent
        effective_hold = hold_duration if hold_duration is not None else self.hold_duration
        effective_ramp = ramp_duration if ramp_duration is not None else self.ramp_duration

        # Ramp to initialize point
        parent_qubit.ramp_to_point(
            "initialize",
            ramp_duration=effective_ramp,
            duration=effective_hold,
        )


@quam_dataclass
class MeasureMacroRF(QuamMacro):
    """Macro for measurement with RF readout and voltage ramp.

    This macro:
    1. Ramps to the 'measure' voltage point (PSB configuration)
    2. Applies RF tone for sensor dot readout
    3. Performs demodulated measurement (I, Q)
    4. Thresholds the signal to determine qubit state

    Attributes:
        ramp_duration: Duration of voltage ramp in ns.
        hold_duration: Total duration at measure point in ns.
        rf_pulse_name: Name of the RF readout pulse.
        rf_duration: Duration of RF readout pulse in ns.
        settle_time_ns: Time to wait before RF pulse for voltage settling.
    """

    ramp_duration: int = 1000
    hold_duration: int = 800_000
    rf_pulse_name: str = "readout"
    rf_duration: int = 10_000
    settle_time_ns: int = 1000

    def apply(self, **kwargs) -> int:
        """Execute measurement sequence and return qubit state.

        Returns:
            Integer QUA variable: 0 for ground state, 1 for excited state.
        """
        parent_qubit = self.parent.parent

        # Ramp to measure point
        parent_qubit.ramp_to_point(
            "measure",
            ramp_duration=kwargs.get("ramp_duration", self.ramp_duration),
            duration=kwargs.get("hold_duration", self.hold_duration),
        )

        # Get sensor dot for readout
        sensor_dot = parent_qubit.sensor_dots[0]

        # Wait for voltage settling
        sensor_dot.readout_resonator.wait(self.settle_time_ns // 4)

        # Declare QUA variables for I/Q
        I = declare(fixed)
        Q = declare(fixed)

        # Apply RF readout pulse and measure
        sensor_dot.readout_resonator.measure(
            self.rf_pulse_name,
            qua_vars=(I, Q),
        )

        # Get threshold from sensor_dot
        qd_pair_id = parent_qubit.machine.find_quantum_dot_pair(
            parent_qubit.quantum_dot.id, parent_qubit.preferred_readout_quantum_dot
        )
        threshold = sensor_dot.readout_thresholds.get(qd_pair_id, 0.0)

        # Threshold I component to get state
        state = declare(int)
        assign(state, Cast.to_int(I > threshold))

        return state


@quam_dataclass
class GateMacro(QuamMacro):
    """Macro for playing RB gates via switch/case.

    This macro plays Gaussian pulses for physical rotations (X90, Y90, X180, Y180)
    and applies frame rotations for virtual Z gates.

    Gate mapping:
        0: X90 (sx)
        1: X180 (x)
        2: Y90
        3: Y180
        4: RZ(pi/2)
        5: RZ(pi)
        6: RZ(3pi/2)
        7: Idle

    Attributes:
        x90_pulse: Name of the X90 pulse operation.
        x180_pulse: Name of the X180 pulse operation.
        y90_pulse: Name of the Y90 pulse operation.
        y180_pulse: Name of the Y180 pulse operation.
    """

    x90_pulse: str = "X90"
    x180_pulse: str = "X180"
    y90_pulse: str = "Y90"
    y180_pulse: str = "Y180"

    def apply(self, gate_int, **kwargs):
        """Execute a single gate based on integer encoding.

        Args:
            gate_int: Integer representing the gate (0-7).
        """
        parent_qubit = self.parent.parent
        xy = parent_qubit.xy_channel

        with switch_(gate_int, unsafe=True):
            with case_(0):  # X90 (sx)
                xy.play(self.x90_pulse)
            with case_(1):  # X180 (x)
                xy.play(self.x180_pulse)
            with case_(2):  # Y90
                xy.play(self.y90_pulse)
            with case_(3):  # Y180
                xy.play(self.y180_pulse)
            with case_(4):  # RZ(pi/2)
                frame_rotation_2pi(0.25, xy.name)
            with case_(5):  # RZ(pi)
                frame_rotation_2pi(0.5, xy.name)
            with case_(6):  # RZ(3pi/2)
                frame_rotation_2pi(0.75, xy.name)
            with case_(7):  # Idle
                xy.wait(4)  # Minimum wait


@quam_dataclass
class CompensationMacro(QuamMacro):
    """Macro for applying compensation pulse.

    Attributes:
        duration: Compensation pulse duration in ns.
    """

    duration: int = 1_000_000

    def apply(self, duration: int = None, **kwargs):
        """Apply compensation pulse to reset DC bias.

        Args:
            duration: Optional override for compensation duration.
        """
        parent_qubit = self.parent.parent
        effective_duration = duration if duration is not None else self.duration

        # Step to zero first
        parent_qubit.step_to_voltages({parent_qubit.quantum_dot.id: 0.0}, duration=16)
        align()

        # Apply compensation using voltage sequence
        parent_qubit.voltage_sequence.apply_compensation_pulse()

        # Hold at zero for remaining time
        remaining = effective_duration - 16  # Approximate
        if remaining > 0:
            wait(remaining // 4)


# =============================================================================
# SECTION 3: Qubit Collection for Batching
# =============================================================================


@dataclass
class QubitBatch:
    """Container for a batch of qubits with indexed access."""

    qubits: List[LDQubit]
    start_index: int = 0

    def items(self):
        """Iterate over (global_index, qubit) pairs."""
        for local_idx, qubit in enumerate(self.qubits):
            yield self.start_index + local_idx, qubit

    def __len__(self):
        return len(self.qubits)


class QubitCollection:
    """Collection of qubits supporting batched execution."""

    def __init__(self, qubits: List[LDQubit], batch_size: int = 1):
        self.qubits = qubits
        self.batch_size = batch_size

    def batch(self):
        """Yield batches of qubits with global index tracking."""
        for i in range(0, len(self.qubits), self.batch_size):
            yield QubitBatch(
                qubits=self.qubits[i : i + self.batch_size],
                start_index=i,
            )


# =============================================================================
# SECTION 4: Machine Configuration
# =============================================================================


def create_spin_qubit_machine():
    """Create a machine configuration for spin qubit RB.

    Returns:
        Tuple of (machine, xy_drives dict, readout_resonators dict)
    """
    machine = LossDiVincenzoQuam()

    controller = "con1"
    lf_fem_slot = 2
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
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=4,
            output_mode="direct",
        ),
        opx_output_Q=LFFEMAnalogOutputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=5,
            output_mode="direct",
        ),
        opx_input_I=LFFEMAnalogInputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=1,
        ),
        opx_input_Q=LFFEMAnalogInputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=2,
        ),
        frequency_converter_up=FrequencyConverter(
            local_oscillator=LocalOscillator(frequency=200e6),
        ),
        intermediate_frequency=50e6,
        operations={
            "readout": pulses.SquareReadoutPulse(
                length=10000,  # 10 us
                amplitude=0.1,
                integration_weights_angle=0.0,
            )
        },
    )

    # XY Drive channels for each qubit
    xy_drives = {}
    for i in range(1, 3):
        xy_drives[i] = XYDrive(
            id=f"Q{i}_xy",
            opx_output=MWFEMAnalogOutputPort(
                controller_id=controller,
                fem_id=mw_fem_slot,
                port_id=i,
                upconverter_frequency=5e9,
                band=2,
                full_scale_power_dbm=10,
            ),
            intermediate_frequency=100e6,
            add_default_pulses=True,
        )

        # Add Gaussian pulses for RB gates (~500 ns)
        gate_length = 500  # ns
        sigma = gate_length / 6

        # X90 (pi/2 pulse)
        xy_drives[i].operations["X90"] = pulses.GaussianPulse(
            length=gate_length, amplitude=0.1, sigma=sigma
        )
        # X180 (pi pulse)
        xy_drives[i].operations["X180"] = pulses.GaussianPulse(
            length=gate_length, amplitude=0.2, sigma=sigma
        )
        # Y90 (pi/2 pulse about Y - same amplitude, different phase handled by frame)
        xy_drives[i].operations["Y90"] = pulses.GaussianPulse(
            length=gate_length, amplitude=0.1, sigma=sigma
        )
        # Y180 (pi pulse about Y)
        xy_drives[i].operations["Y180"] = pulses.GaussianPulse(
            length=gate_length, amplitude=0.2, sigma=sigma
        )

    # Virtual gate set
    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": plungers[1],
            "virtual_dot_2": plungers[2],
            "virtual_sensor_1": sensor_dc,
        },
        gate_set_id="main_qpu",
        compensation_matrix=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
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


def register_qubit_with_rb_macros(
    machine: LossDiVincenzoQuam,
    xy_drives: dict,
    rb_config: RBConfig,
) -> List[LDQubit]:
    """Register qubits with voltage points and RB macros.

    Args:
        machine: The configured machine instance.
        xy_drives: Dictionary of XY drive channels.
        rb_config: RB experiment configuration.

    Returns:
        List of registered LDQubit instances.
    """
    qubit_configs = [
        ("Q1", "virtual_dot_1", "virtual_dot_2", 1),
    ]

    qubits = []

    for qubit_name, dot_id, readout_dot_id, xy_idx in qubit_configs:
        machine.register_qubit(
            qubit_name=qubit_name,
            quantum_dot_id=dot_id,
            xy_channel=xy_drives[xy_idx],
            readout_quantum_dot=readout_dot_id,
        )

        qubit = machine.qubits[qubit_name]

        # Define voltage points for RB sequence
        # Initialize point (electron loading)
        qubit.add_point_with_step_macro(
            "initialize",
            voltages={dot_id: 0.05},
            duration=rb_config.init_duration_ns,
        )

        # Operate point (manipulation sweet spot)
        qubit.add_point(
            "operate",
            voltages={dot_id: 0.0},
        )

        # Measure point (PSB readout)
        qubit.add_point(
            "measure",
            voltages={dot_id: -0.05},
        )

        # Register RB-specific macros
        qubit.macros["init_rb"] = InitMacro(
            ramp_duration=rb_config.ramp_duration_ns,
            hold_duration=rb_config.init_duration_ns,
        )
        qubit.macros["measure_rb"] = MeasureMacroRF(
            ramp_duration=rb_config.ramp_duration_ns,
            hold_duration=rb_config.measure_duration_ns,
            rf_duration=rb_config.rf_readout_duration_ns,
        )
        qubit.macros["gate"] = GateMacro()
        qubit.macros["compensate"] = CompensationMacro(
            duration=rb_config.compensation_duration_ns,
        )

        qubits.append(qubit)

    return qubits


# =============================================================================
# SECTION 5: QUA Program Generation
# =============================================================================


def play_rb_gate(qubit: LDQubit, gate_int):
    """Play a single RB gate on a qubit.

    Args:
        qubit: The qubit to apply the gate on.
        gate_int: Integer representing the gate (0-7).
    """
    xy = qubit.xy_channel

    with switch_(gate_int, unsafe=True):
        with case_(0):  # X90 (sx)
            xy.play("X90")
        with case_(1):  # X180 (x)
            xy.play("X180")
        with case_(2):  # Y90
            # Apply pi/2 frame rotation then X90
            frame_rotation_2pi(0.25, xy.name)
            xy.play("X90")
            frame_rotation_2pi(-0.25, xy.name)
        with case_(3):  # Y180
            # Apply pi/2 frame rotation then X180
            frame_rotation_2pi(0.25, xy.name)
            xy.play("X180")
            frame_rotation_2pi(-0.25, xy.name)
        with case_(4):  # RZ(pi/2)
            frame_rotation_2pi(0.25, xy.name)
        with case_(5):  # RZ(pi)
            frame_rotation_2pi(0.5, xy.name)
        with case_(6):  # RZ(3pi/2)
            frame_rotation_2pi(0.75, xy.name)
        with case_(7):  # Idle
            xy.wait(4)


def create_rb_qua_program(
    machine: LossDiVincenzoQuam,
    qubit: LDQubit,
    rb_config: RBConfig,
    circuits_as_ints: Dict[int, List[List[int]]],
    max_circuit_length: int,
):
    """Create the QUA program for single-qubit RB.

    This is a simplified version for a single qubit without batching.
    Python-level timing is used to measure total execution time.

    Args:
        machine: The configured machine instance.
        qubit: The single LDQubit to run RB on.
        rb_config: RB experiment configuration.
        circuits_as_ints: Dictionary mapping depths to circuit integer sequences.
        max_circuit_length: Maximum number of gates in any circuit.

    Returns:
        QUA program for the RB experiment.
    """
    num_depths = len(rb_config.circuit_lengths)
    num_circuits = rb_config.num_circuits_per_length

    # Flatten circuits for QUA array
    # Format: all circuits concatenated, indexed by (depth_idx * num_circuits + circuit_idx)
    all_circuits_flat = []
    circuit_lengths_flat = []

    for depth in rb_config.circuit_lengths:
        for circuit in circuits_as_ints[depth]:
            # Pad circuit to max_circuit_length
            padded = circuit + [7] * (max_circuit_length - len(circuit))  # 7 = idle
            all_circuits_flat.extend(padded)
            circuit_lengths_flat.append(len(circuit))

    with program() as rb_prog:
        # Declare QUA variables
        n = declare(int)  # Shot counter
        n_st = declare_stream()

        depth_idx = declare(int)  # Depth index
        circuit_idx = declare(int)  # Circuit index
        gate_idx = declare(int)  # Gate index within circuit

        # Circuit data
        circuits_qua = declare(int, value=all_circuits_flat)
        circuit_lengths_qua = declare(int, value=circuit_lengths_flat)

        # Current gate and circuit offset
        current_gate = declare(int)
        circuit_offset = declare(int)
        current_circuit_length = declare(int)

        # State variable and stream
        state = declare(int)
        state_st = declare_stream()

        # I/Q variables for readout
        I = declare(fixed)
        Q = declare(fixed)

        # Get sensor dot and threshold for this qubit
        sensor_dot = qubit.sensor_dots[0]
        qd_pair_id = machine.find_quantum_dot_pair(
            qubit.quantum_dot.id, qubit.preferred_readout_quantum_dot
        )
        threshold = sensor_dot.readout_thresholds.get(qd_pair_id, 0.0)

        # Main experiment loop
        with for_(n, 0, n < rb_config.num_shots, n + 1):
            save(n, n_st)

            with for_(depth_idx, 0, depth_idx < num_depths, depth_idx + 1):
                with for_(circuit_idx, 0, circuit_idx < num_circuits, circuit_idx + 1):
                    # Calculate offset into flattened circuit array
                    assign(
                        circuit_offset,
                        (depth_idx * num_circuits + circuit_idx) * max_circuit_length,
                    )
                    assign(
                        current_circuit_length,
                        circuit_lengths_qua[depth_idx * num_circuits + circuit_idx],
                    )

                    # --- Initialization ---
                    # Step to init point and hold for electron loading
                    align()
                    qubit.step_to_point(
                        "initialize",
                        duration=rb_config.init_duration_ns,
                    )

                    # --- Gate Sequence ---
                    # Step to operate point for gate application
                    align()
                    qubit.step_to_point("operate", duration=16)

                    # Play the gate sequence
                    align()
                    with for_(gate_idx, 0, gate_idx < current_circuit_length, gate_idx + 1):
                        assign(current_gate, circuits_qua[circuit_offset + gate_idx])
                        play_rb_gate(qubit, current_gate)

                    # Reset frame after gate sequence
                    reset_frame(qubit.xy_channel.name)

                    # --- Measurement ---
                    # Step to measure point
                    align()
                    qubit.step_to_point(
                        "measure",
                        duration=rb_config.measure_duration_ns,
                    )

                    # RF readout
                    sensor_dot.readout_resonator.wait(250)  # Settle time (1 us)
                    sensor_dot.readout_resonator.measure("readout", qua_vars=(I, Q))

                    # Threshold to get state
                    assign(state, Cast.to_int(I > threshold))

                    # --- Compensation ---
                    align()
                    qubit.voltage_sequence.apply_compensation_pulse()

                    # Wait for compensation pulse duration
                    wait(rb_config.compensation_duration_ns // 4)

                    # --- Save Result ---
                    save(state, state_st)

        # Stream processing
        with stream_processing():
            n_st.save("iteration")
            state_st.buffer(num_circuits).buffer(num_depths).buffer(rb_config.num_shots).save(
                "state"
            )

    return rb_prog


# =============================================================================
# SECTION 6: Main Entry Point
# =============================================================================


def setup_rb_experiment(rb_config: RBConfig = None):
    """Set up all components for the single-qubit RB experiment.

    Args:
        rb_config: Optional RB configuration. Uses defaults if not provided.

    Returns:
        Tuple of (machine, qubit, rb_program, rb_generator, rb_config)
    """
    if rb_config is None:
        rb_config = RBConfig()

    print("Generating RB circuits...")
    rb_generator = SingleQubitStandardRB(
        circuit_lengths=rb_config.circuit_lengths,
        num_circuits_per_length=rb_config.num_circuits_per_length,
        seed=rb_config.seed,
    )

    circuits_as_ints, max_circuit_length, total_circuits = prepare_circuits_for_qua(rb_generator)

    print(f"  Generated {total_circuits} circuits")
    print(f"  Max circuit length: {max_circuit_length} gates")

    # Estimate experiment time
    time_est = estimate_total_experiment_time(
        rb_config.circuit_lengths,
        rb_config.num_circuits_per_length,
        rb_config.num_shots,
        rb_config.gate_duration_ns,
        rb_config.init_duration_ns / 1000,  # Convert to us
        rb_config.measure_duration_ns / 1000,
        rb_config.compensation_duration_ns / 1000,
    )
    print(f"  Estimated experiment time: {time_est['total_time_hours']:.1f} hours")

    print("\nConfiguring machine...")
    machine, xy_drives, readout_resonators = create_spin_qubit_machine()

    qubits_list = register_qubit_with_rb_macros(machine, xy_drives, rb_config)
    qubit = qubits_list[0]  # Single qubit

    print(f"  Registered qubit: {qubit.id}")

    print("\nCreating QUA program...")
    rb_program = create_rb_qua_program(
        machine,
        qubit,
        rb_config,
        circuits_as_ints,
        max_circuit_length,
    )

    return machine, qubit, rb_program, rb_generator, rb_config


def analyze_rb_results(
    results: dict,
    rb_config: RBConfig,
) -> SingleQubitRBResult:
    """Analyze RB results and return fidelity metrics.

    Args:
        results: Dictionary of results from the QUA job.
        rb_config: RB experiment configuration.

    Returns:
        SingleQubitRBResult with analysis.
    """
    state_data = results["state"]

    # Reshape to (depths, circuits, shots)
    state_array = np.array(state_data).reshape(
        len(rb_config.circuit_lengths),
        rb_config.num_circuits_per_length,
        rb_config.num_shots,
    )

    rb_result = SingleQubitRBResult(
        circuit_depths=rb_config.circuit_lengths,
        num_circuits_per_length=rb_config.num_circuits_per_length,
        num_averages=rb_config.num_shots,
        state=state_array,
    )

    return rb_result


# =============================================================================
# SECTION 7: Execution
# =============================================================================


def run_rb_with_timing(rb_config: RBConfig = None):
    """Run the full RB experiment with Python-level timing.

    Args:
        rb_config: RB configuration. Uses defaults if not provided.

    Returns:
        Tuple of (machine, qubit, rb_program, rb_config, setup_time_s)
    """
    import time

    print("=" * 60)
    print("Single-Qubit Randomized Benchmarking for Spin Qubits")
    print("=" * 60)

    # Time the setup
    t_start = time.time()
    machine, qubit, rb_program, rb_generator, rb_config = setup_rb_experiment(rb_config)
    setup_time = time.time() - t_start

    print(f"\nSetup completed in {setup_time:.2f} seconds")
    print(f"Qubit: {qubit.id}")

    return machine, qubit, rb_program, rb_config, setup_time


if __name__ == "__main__":
    import time

    # Use reduced parameters for testing
    test_config = RBConfig(
        circuit_lengths=[2, 4, 8, 16],  # Reduced for testing
        num_circuits_per_length=5,
        num_shots=10,
        init_duration_ns=10_000,  # Reduced for simulation
        measure_duration_ns=10_000,
        compensation_duration_ns=10_000,
    )

    # Run setup with timing
    machine, qubit, rb_program, rb_config, setup_time = run_rb_with_timing(test_config)

    print(f"\nMachine configured with {len(machine.qubits)} qubit(s)")
    print(f"Qubit: {qubit.id}")

    config = machine.generate_config()

    print("\n" + "=" * 60)
    print("Example: Run with QM Hardware")
    print("=" * 60)
    print(
        """
    import time

    # Connect to QM hardware
    qmm = QuantumMachinesManager(host="...", port=...)
    qm = qmm.open_qm(config)

    # Execute with timing
    t_start = time.time()
    job = qm.execute(rb_program)
    job.result_handles.wait_for_all_values()
    execution_time = time.time() - t_start

    print(f"Execution completed in {execution_time:.2f} seconds")

    # Get results
    results_dict = {
        "state": job.result_handles.get("state").fetch_all(),
    }

    # Analyze RB fidelity
    rb_result = analyze_rb_results(results_dict, rb_config)

    # Plot fidelity
    rb_result.plot_with_fidelity()
    plt.show()

    # Print results
    print(f"Clifford Fidelity: {rb_result.fidelity * 100:.2f}%")
    print(f"Error per Clifford: {rb_result.error_per_clifford * 100:.4f}%")
    """
    )

    print("\n" + "=" * 60)
    print("Example: Run with QM Cloud Simulator")
    print("=" * 60)
    # print("""
    import time
    from configs import EMAIL, PASSWORD
    import qm_saas

    client = qm_saas.QmSaas(
        email=EMAIL,
        password=PASSWORD,
        host="qm-saas.dev.quantum-machines.co",
    )

    with client.simulator(client.latest_version()) as instance:
        qmm = QuantumMachinesManager(
            host=instance.host,
            port=instance.port,
            connection_headers=instance.default_connection_headers,
        )

        # Simulate with timing
        t_start = time.time()
        simulation_config = SimulationConfig(duration=12000)
        job = qmm.simulate(config, rb_program, simulation_config)
        job.wait_until("Done", timeout=60)
        simulation_time = time.time() - t_start

        print(f"Simulation completed in {simulation_time:.2f} seconds")

        # Get simulated samples
        simulated_samples = job.get_simulated_samples()
        simulated_samples.con1.plot()
        plt.show()
    # """)

    print(f"\nSetup time: {setup_time:.2f} seconds")
    print("Ready for execution!")
