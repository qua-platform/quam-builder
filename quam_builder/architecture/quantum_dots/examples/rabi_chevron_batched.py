"""
Rabi Chevron Experiment Example - Batched Qubits Version
=========================================================

This example demonstrates a Rabi chevron experiment using the batched qubits pattern
with voltage point macros. It shows how to:

1. Configure a minimal quantum dot machine with virtual gates
2. Define voltage points and associated step macros
3. Create custom X180 and Measure macros
4. Build a QUA program using the batched qubit iteration pattern

Key Features:
-------------
- Uses `machine.declare_qua_variables()` for standardized variable declaration
- `StepPointMacro` (via add_point_with_step_macro): Steps to voltage points
- `X180Macro`: Applies X180 (pi) pulse with variable duration
- `MeasureMacro`: Steps to 'readout' point, measures I/Q, thresholds I component

Thresholding:
-------------
The MeasureMacro uses the sensor_dot's calibrated threshold on the I component:
    state = I > threshold

Experiment Sequence:
--------------------
1. Set drive frequency and reset phase
2. Empty: Step to empty point to deplete dots
3. Pre-measure: Get initial state p1 (for comparison)
4. Initialize: Step to initialize point and load electron (variable duration)
5. X180: Apply pi pulse with variable duration
6. Measure: Step to readout point, measure, threshold → parity p2
7. Compensate: Apply compensation pulse to reset DC bias
8. Save: p1, p2, and pdiff (state difference)
"""

from typing import List
from dataclasses import dataclass

from qm.qua import (
    program,
    for_,
    for_each_,
    declare,
    declare_stream,
    fixed,
    update_frequency,
    align,
    save,
    stream_processing,
    if_,
    else_,
    assign,
    Cast,
    reset_if_phase,
)
from qm import SimulationConfig, QuantumMachinesManager
import qm_saas
import matplotlib

matplotlib.use("TkAgg")
# pylint: disable=wrong-import-position
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
from quam.utils.qua_types import QuaVariableBool

from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    XYDrive,
)
from quam_builder.architecture.quantum_dots.components.readout_resonator import (
    ReadoutResonatorIQ,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit

# pylint: enable=wrong-import-position


# =============================================================================
# SECTION 1: Custom Macros (Initialize and Measure with voltage point navigation)
# =============================================================================


@quam_dataclass
class X180Macro(QuamMacro):  # pylint: disable=too-few-public-methods
    """Macro for X180 gate: step to operate point and apply pi pulse.

    This macro:
    1. Steps to the 'operate' voltage point (manipulation sweet spot)
    2. Applies the X180 (pi) pulse with variable duration

    Attributes:
        pulse_name: Name of the pulse operation to play (default: "X180")
        amplitude_scale: Optional amplitude scaling factor
    """

    pulse_name: str = "X180"
    amplitude_scale: float = None
    duration: int = None

    def _validate(self, xy_channel, duration, amplitude_scale) -> None:
        """Validate parameters for X180 gate execution.

        Raises:
            ValueError: If xy_channel is None or required parameters are missing.
        """
        if xy_channel is None:
            raise ValueError(
                "Cannot apply X180 gate: xy_channel is not configured on parent qubit."
            )

        missing = []
        if duration is None:
            missing.append("duration")
        if amplitude_scale is None:
            missing.append("amplitude_scale")
        if missing:
            raise ValueError(
                f"Missing required parameter(s): {', '.join(missing)}. "
                "Provide via kwargs or set as class attributes."
            )

    def apply(self, duration: int = None, **kwargs) -> None:
        """Execute X180 gate sequence.

        Args:
            duration: Pulse duration in clock cycles (4ns each)
        """
        parent_qubit = self.parent.parent
        amp_scale = kwargs.get("amplitude_scale", self.amplitude_scale)
        # Use positional arg if provided, otherwise check kwargs, then fall back to default
        if duration is None:
            duration = kwargs.get("duration", self.duration)

        self._validate(parent_qubit.xy_channel, duration, amp_scale)

        parent_qubit.xy_channel.play(
            self.pulse_name,
            amplitude_scale=amp_scale,
            duration=duration,
        )


@quam_dataclass
class MeasureMacro(QuamMacro):  # pylint: disable=too-few-public-methods
    """Macro for measurement with integrated voltage point navigation and thresholding.

    This macro:
    1. Steps to the 'readout' voltage point (PSB configuration)
    2. Performs demodulated measurement (I, Q)
    3. Thresholds the I component: state = I > threshold

    The threshold is retrieved from the sensor_dot's readout_thresholds
    dictionary, keyed by the quantum_dot_pair_id.

    Attributes:
        pulse_name: Name of the readout pulse operation (default: "readout")
        readout_duration: Hold duration at readout point (ns)
    """

    pulse_name: str = "readout"
    readout_duration: int = 2000

    def _validate(self, parent_qubit) -> None:
        """Validate that the qubit is properly configured for measurement.

        Raises:
            ValueError: If required components are missing or misconfigured.
        """
        if not parent_qubit.sensor_dots:
            raise ValueError("Cannot measure: no sensor_dots configured on parent qubit.")

        sensor_dot = parent_qubit.sensor_dots[0]

        if sensor_dot.readout_resonator is None:
            raise ValueError("Cannot measure: readout_resonator is not configured on sensor_dot.")

        if parent_qubit.quantum_dot is None:
            raise ValueError("Cannot measure: quantum_dot is not configured on parent qubit.")

        if parent_qubit.preferred_readout_quantum_dot is None:
            raise ValueError(
                "Cannot measure: preferred_readout_quantum_dot is not set on parent qubit."
            )

    def apply(self, **kwargs) -> QuaVariableBool:
        """Execute measurement sequence and return qubit state (parity).

        The measurement thresholds the I quadrature component to determine state.

        Returns:
            Boolean QUA variable indicating qubit state (True = I > threshold)
        """
        pulse = kwargs.get("pulse_name", self.pulse_name)

        # Navigate to qubit
        parent_qubit = self.parent.parent

        self._validate(parent_qubit)

        # Step to readout point (PSB configuration) - integrated into measure
        parent_qubit.step_to_point("measure", duration=self.readout_duration)

        # Get the associated sensor dot and quantum dot pair info
        sensor_dot = parent_qubit.sensor_dots[0]

        # Get the quantum_dot_pair_id for looking up threshold/projector
        qd_pair_id = parent_qubit.machine.find_quantum_dot_pair(
            parent_qubit.quantum_dot.id, parent_qubit.preferred_readout_quantum_dot
        )

        # Declare QUA variables for I and Q quadratures
        I = declare(fixed)
        Q = declare(fixed)

        # Wait for transients, then perform measurement
        sensor_dot.readout_resonator.wait(64)
        sensor_dot.readout_resonator.measure(
            pulse,
            qua_vars=(I, Q),
        )

        # Get threshold from sensor_dot (default to 0.0)
        threshold = sensor_dot.readout_thresholds.get(qd_pair_id, 0.0)

        # Threshold I component to get state
        state = declare(bool)
        assign(state, I > threshold)

        return state


# =============================================================================
# SECTION 2: Qubit Collection for Batching
# =============================================================================


@dataclass
class QubitBatch:  # pylint: disable=too-few-public-methods
    """Container for a batch of qubits with indexed access.

    Provides iteration over qubits with GLOBAL index tracking for use in
    batched QUA programs where results need to be saved per-qubit to
    globally indexed arrays/streams.

    Attributes:
        qubits: List of qubits in this batch
        start_index: Global index of the first qubit in this batch
    """

    qubits: List[LDQubit]
    start_index: int = 0

    def items(self):
        """Iterate over (global_index, qubit) pairs."""
        for local_idx, qubit in enumerate(self.qubits):
            yield self.start_index + local_idx, qubit

    def __len__(self):
        return len(self.qubits)


class QubitCollection:  # pylint: disable=too-few-public-methods
    """Collection of qubits supporting batched execution.

    Provides a batch() method that yields QubitBatch objects for
    iteration in QUA programs. Batches track global indices for
    correct stream/array indexing.
    """

    def __init__(self, qubits: List[LDQubit], batch_size: int = 1):
        self.qubits = qubits
        self.batch_size = batch_size

    def batch(self):
        """Yield batches of qubits with global index tracking.

        Each QubitBatch knows its starting index in the global qubit list,
        so items() returns (global_index, qubit) pairs.
        """
        for i in range(0, len(self.qubits), self.batch_size):
            yield QubitBatch(
                qubits=self.qubits[i : i + self.batch_size],
                start_index=i,
            )


# =============================================================================
# SECTION 3: Create Machine and Physical Channels
# =============================================================================


def create_minimal_machine():
    """Create a machine configuration with 4 qubits in two pairs.

    Qubit pairs:
    - Q1 and Q2: virtual_dot_1 and virtual_dot_2, with virtual_sensor_1 (LF-FEM slot 2)
    - Q3 and Q4: virtual_dot_3 and virtual_dot_4, with virtual_sensor_2 (LF-FEM slot 3)

    Returns:
        Tuple of (machine, xy_drives dict, readout_resonators dict)
    """
    # pylint: disable=unexpected-keyword-arg
    # Note: pylint doesn't understand quam_dataclass dynamic constructors
    machine = LossDiVincenzoQuam()

    controller = "con1"
    lf_fem_slot_1 = 2  # For qubit pair 1 (Q1, Q2)
    lf_fem_slot_2 = 3  # For qubit pair 2 (Q3, Q4)
    mw_fem_slot = 1

    # -------------------------------------------------------------------------
    # Physical Voltage Channels (4 plungers + 2 sensors)
    # Each pair uses its own LF-FEM slot
    # -------------------------------------------------------------------------
    plungers = {}
    # Pair 1: plungers 1 and 2 on LF-FEM slot 2
    for i in range(1, 3):
        plungers[i] = VoltageGate(
            id=f"plunger_{i}",
            opx_output=LFFEMAnalogOutputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_1,
                port_id=i,
                output_mode="direct",
            ),
            sticky=StickyChannelAddon(duration=16, digital=False),
        )
    # Pair 2: plungers 3 and 4 on LF-FEM slot 3
    for i in range(3, 5):
        plungers[i] = VoltageGate(
            id=f"plunger_{i}",
            opx_output=LFFEMAnalogOutputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_2,
                port_id=i - 2,  # ports 1 and 2
                output_mode="direct",
            ),
            sticky=StickyChannelAddon(duration=16, digital=False),
        )

    # Sensor DC channels
    sensor_dcs = {
        1: VoltageGate(
            id="sensor_DC_1",
            opx_output=LFFEMAnalogOutputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_1,
                port_id=3,
                output_mode="direct",
            ),
            sticky=StickyChannelAddon(duration=16, digital=False),
        ),
        2: VoltageGate(
            id="sensor_DC_2",
            opx_output=LFFEMAnalogOutputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_2,
                port_id=3,
                output_mode="direct",
            ),
            sticky=StickyChannelAddon(duration=16, digital=False),
        ),
    }

    # -------------------------------------------------------------------------
    # Readout Resonators (2 IQ resonators, one per qubit pair)
    # Each on its own LF-FEM slot
    # -------------------------------------------------------------------------
    readout_resonators = {
        1: ReadoutResonatorIQ(
            id="sensor_resonator_1",
            opx_output_I=LFFEMAnalogOutputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_1,
                port_id=4,
                output_mode="direct",
            ),
            opx_output_Q=LFFEMAnalogOutputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_1,
                port_id=5,
                output_mode="direct",
            ),
            opx_input_I=LFFEMAnalogInputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_1,
                port_id=1,
            ),
            opx_input_Q=LFFEMAnalogInputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_1,
                port_id=2,
            ),
            frequency_converter_up=FrequencyConverter(
                local_oscillator=LocalOscillator(frequency=5e9),
            ),
            intermediate_frequency=50e6,
            operations={
                "readout": pulses.SquareReadoutPulse(
                    length=1000,
                    amplitude=0.1,
                    integration_weights_angle=0.0,
                )
            },
        ),
        2: ReadoutResonatorIQ(
            id="sensor_resonator_2",
            opx_output_I=LFFEMAnalogOutputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_2,
                port_id=4,
                output_mode="direct",
            ),
            opx_output_Q=LFFEMAnalogOutputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_2,
                port_id=5,
                output_mode="direct",
            ),
            opx_input_I=LFFEMAnalogInputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_2,
                port_id=1,
            ),
            opx_input_Q=LFFEMAnalogInputPort(
                controller_id=controller,
                fem_id=lf_fem_slot_2,
                port_id=2,
            ),
            frequency_converter_up=FrequencyConverter(
                local_oscillator=LocalOscillator(frequency=5e9),
            ),
            intermediate_frequency=50e6,
            operations={
                "readout": pulses.SquareReadoutPulse(
                    length=1000,
                    amplitude=0.1,
                    integration_weights_angle=0.0,
                )
            },
        ),
    }

    # -------------------------------------------------------------------------
    # XY Drive Channels (4 channels, one per qubit)
    # -------------------------------------------------------------------------
    xy_drives = {}
    for i in range(1, 5):
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
        length = 100
        xy_drives[i].operations["X180"] = pulses.GaussianPulse(
            length=length, amplitude=0.2, sigma=length / 6
        )

    # -------------------------------------------------------------------------
    # Virtual Gate Set (all 4 dots + 2 sensors)
    # -------------------------------------------------------------------------
    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": plungers[1],
            "virtual_dot_2": plungers[2],
            "virtual_dot_3": plungers[3],
            "virtual_dot_4": plungers[4],
            "virtual_sensor_1": sensor_dcs[1],
            "virtual_sensor_2": sensor_dcs[2],
        },
        gate_set_id="main_qpu",
        compensation_matrix=[
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ],
    )

    # -------------------------------------------------------------------------
    # Register Channel Elements
    # -------------------------------------------------------------------------
    machine.register_channel_elements(
        plunger_channels=list(plungers.values()),
        sensor_resonator_mappings={
            sensor_dcs[1]: readout_resonators[1],
            sensor_dcs[2]: readout_resonators[2],
        },
        barrier_channels=[],
    )

    # -------------------------------------------------------------------------
    # Register Quantum Dot Pairs
    # -------------------------------------------------------------------------
    # Pair 1: dots 1 and 2, with sensor 1
    machine.register_quantum_dot_pair(
        quantum_dot_ids=["virtual_dot_1", "virtual_dot_2"],
        sensor_dot_ids=["virtual_sensor_1"],
        id="qd_pair_1_2",
    )

    # Pair 2: dots 3 and 4, with sensor 2
    machine.register_quantum_dot_pair(
        quantum_dot_ids=["virtual_dot_3", "virtual_dot_4"],
        sensor_dot_ids=["virtual_sensor_2"],
        id="qd_pair_3_4",
    )

    # -------------------------------------------------------------------------
    # Configure readout thresholds for sensor dots
    # -------------------------------------------------------------------------
    # pylint: disable=unsubscriptable-object
    sensor_dot_1 = machine.sensor_dots["virtual_sensor_1"]
    sensor_dot_1._add_readout_params(quantum_dot_pair_id="qd_pair_1_2", threshold=0.5)

    sensor_dot_2 = machine.sensor_dots["virtual_sensor_2"]
    sensor_dot_2._add_readout_params(quantum_dot_pair_id="qd_pair_3_4", threshold=0.5)
    # pylint: enable=unsubscriptable-object

    return machine, xy_drives, readout_resonators


# =============================================================================
# SECTION 4: Register Qubit with Voltage Points and Macros
# =============================================================================


def register_qubits_with_points(
    machine: LossDiVincenzoQuam,
    xy_drives: dict,
) -> List[LDQubit]:
    """Register 4 LDQubits with voltage points and custom macros.

    Qubit pairing for preferred readout:
    - Q1 uses virtual_dot_1, prefers readout via virtual_dot_2
    - Q2 uses virtual_dot_2, prefers readout via virtual_dot_1
    - Q3 uses virtual_dot_3, prefers readout via virtual_dot_4
    - Q4 uses virtual_dot_4, prefers readout via virtual_dot_3

    Args:
        machine: The configured machine instance
        xy_drives: Dictionary of XY drive channels keyed by qubit index (1-4)

    Returns:
        List of registered LDQubit instances
    """
    # Define qubit configurations: (qubit_name, dot_id, readout_dot_id, xy_index)
    qubit_configs = [
        ("Q1", "virtual_dot_1", "virtual_dot_2", 1),
        ("Q2", "virtual_dot_2", "virtual_dot_1", 2),
        ("Q3", "virtual_dot_3", "virtual_dot_4", 3),
        ("Q4", "virtual_dot_4", "virtual_dot_3", 4),
    ]

    qubits = []

    for qubit_name, dot_id, readout_dot_id, xy_idx in qubit_configs:
        # Register the qubit
        machine.register_qubit(
            qubit_name=qubit_name,
            quantum_dot_id=dot_id,
            xy_channel=xy_drives[xy_idx],
            readout_quantum_dot=readout_dot_id,
        )

        qubit = machine.qubits[qubit_name]  # pylint: disable=unsubscriptable-object

        # Define voltage points based on which pair this qubit belongs to
        if xy_idx <= 2:
            # Pair 1: dots 1 and 2
            dot_keys = ["virtual_dot_1", "virtual_dot_2"]
        else:
            # Pair 2: dots 3 and 4
            dot_keys = ["virtual_dot_3", "virtual_dot_4"]

        # Define Voltage Points and create step macros
        qubit.add_point_with_step_macro(
            "empty",
            voltages={f"virtual_dot_{xy_idx}": -0.1},
            duration=500,
        )
        qubit.add_point_with_step_macro(
            "initialize",
            voltages={f"virtual_dot_{xy_idx}": 0.05},
            duration=500,
        )
        qubit.add_point(
            "measure",
            voltages={f"virtual_dot_{xy_idx}": -0.05},
        )

        # Register custom macros
        qubit.macros["x180"] = X180Macro(pulse_name="X180", amplitude_scale=1.0)
        qubit.macros["measure"] = MeasureMacro(
            pulse_name="readout",
            readout_duration=2000,
        )

        qubits.append(qubit)

    return qubits


# =============================================================================
# SECTION 5: Create the Rabi Chevron QUA Program (Batched Version)
# =============================================================================


def create_rabi_chevron_program_batched(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    machine: LossDiVincenzoQuam,
    qubits: QubitCollection,
    n_avg: int = 1,
    pulse_durations: List[int] = None,
    frequencies: List[int] = None,
    wait_time: int = 64,
):
    """
    Create the Rabi chevron QUA program using batched qubit pattern.

    This follows the node-based workflow pattern:
        with program() as node.namespace["qua_program"]:
            p1, p2, ... = node.machine.declare_qua_variables()

    Args:
        machine: The configured machine instance
        qubits: QubitCollection supporting batched execution
        n_avg: Number of averages
        pulse_durations: List of pulse durations (clock cycles)
        frequencies: List of frequencies (Hz)

    Returns:
        QUA program for the Rabi chevron experiment
    """
    # Default sweep parameters
    if pulse_durations is None:
        pulse_durations = [
            250,
        ]  # clock cycles (4ns each)
    if frequencies is None:
        frequencies = [
            int(10e6),
        ]  # Hz

    num_qubits = len(qubits.qubits)

    with program() as rabi_chevron:
        # Declare QUA variables using machine's method
        # Returns: (I_list, I_st_list, Q_list, Q_st_list, n, n_st)
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables(num_IQ_pairs=num_qubits)

        # Additional variables for pre/post measurement comparison
        # Use int instead of bool so we can average in stream processing
        p1 = declare(int, size=num_qubits)
        p2 = declare(int, size=num_qubits)
        pdiff = declare(int, size=num_qubits)
        p1_st = [declare_stream() for _ in range(num_qubits)]
        p2_st = [declare_stream() for _ in range(num_qubits)]
        pdiff_st = [declare_stream() for _ in range(num_qubits)]

        # Sweep variables
        pulse_duration = declare(int)
        frequency = declare(int)

        # Main experiment loop
        for batched_qubits in qubits.batch():
            with for_(n, 0, n < n_avg, n + 1):
                save(n, n_st)

                with for_each_(pulse_duration, pulse_durations):
                    with for_each_(frequency, frequencies):
                        # ---------------------------------------------------------
                        # Pre-measurement: Check initial state
                        # ---------------------------------------------------------
                        for i, qubit in batched_qubits.items():
                            # Set drive frequency for this iteration
                            update_frequency(qubit.xy_channel.name, frequency)
                            reset_if_phase(qubit.xy_channel.name)

                        # ---------------------------------------------------------
                        # Step 1: Empty - step to empty point (fixed duration)
                        # ---------------------------------------------------------
                        align()
                        with machine.get_voltage_sequence("main_qpu").simultaneous(duration=500):
                            for i, qubit in batched_qubits.items():
                                qubit.empty()

                        align()
                        with machine.get_voltage_sequence("main_qpu").simultaneous(duration=2000):
                            for i, qubit in batched_qubits.items():
                                # Measure initial state (includes step_to('readout'))
                                # Cast bool to int for stream averaging
                                assign(p1[i], Cast.to_int(qubit.measure()))

                        # ---------------------------------------------------------
                        # Step 2: Initialize - load electron into dot (variable duration)
                        # ---------------------------------------------------------
                        align()
                        with machine.get_voltage_sequence("main_qpu").simultaneous(
                            duration=4 * (pulse_duration + wait_time)
                        ):
                            for i, qubit in batched_qubits.items():
                                qubit.initialize(hold_duration=4 * (pulse_duration + wait_time))

                        # ---------------------------------------------------------
                        # Step 3: X180 - move to sweet spot and apply pi pulse
                        # ---------------------------------------------------------
                        for i, qubit in batched_qubits.items():
                            # X180 macro handles step_to('operate') + X180 pulse
                            qubit.x180(duration=pulse_duration)

                        # Synchronize before measurement
                        align()

                        # ---------------------------------------------------------
                        # Step 4: Measure - move to PSB and measure
                        # ---------------------------------------------------------
                        with machine.get_voltage_sequence("main_qpu").simultaneous(duration=2000):
                            for i, qubit in batched_qubits.items():
                                # Measure macro handles step_to('readout') + measurement
                                # Cast bool to int for stream averaging
                                assign(p2[i], Cast.to_int(qubit.measure()))

                        # Synchronize before compensation
                        align()

                        # ---------------------------------------------------------
                        # Step 5: Apply compensation pulse to reset DC bias
                        # ---------------------------------------------------------
                        for i, qubit in batched_qubits.items():
                            qubit.voltage_sequence.apply_compensation_pulse()

                        # ---------------------------------------------------------
                        # Save results
                        # ---------------------------------------------------------
                        for i, qubit in batched_qubits.items():
                            save(p1[i], p1_st[i])
                            save(p2[i], p2_st[i])

                            # Calculate state difference
                            with if_(p1[i] == p2[i]):
                                save(0, pdiff_st[i])
                            with else_():
                                save(1, pdiff_st[i])

        # Stream processing
        with stream_processing():
            n_st.save("iteration")

            n_durations = len(pulse_durations)
            n_freqs = len(frequencies)

            for i in range(num_qubits):
                p1_st[i].buffer(n_freqs, n_durations).average().save(f"p1_q{i}")
                p2_st[i].buffer(n_freqs, n_durations).average().save(f"p2_q{i}")
                pdiff_st[i].buffer(n_freqs, n_durations).average().save(f"pdiff_q{i}")

    return rabi_chevron


# =============================================================================
# SECTION 6: Main Entry Point
# =============================================================================


def setup_rabi_chevron_experiment():
    """Set up all components for the Rabi chevron experiment.

    Creates a 4-qubit configuration with two pairs:
    - Q1 and Q2: preferred readout qubits for each other
    - Q3 and Q4: preferred readout qubits for each other

    Batching strategy:
    - Batch 1: Q1 and Q3 (from different pairs, can run in parallel)
    - Batch 2: Q2 and Q4 (from different pairs, can run in parallel)
    """
    # Create machine with 4 qubits in 2 pairs
    machine, xy_drives, readout_resonators = create_minimal_machine()

    # Register all 4 qubits with voltage points and macros
    # Returns [Q1, Q2, Q3, Q4]
    qubit_list = register_qubits_with_points(machine, xy_drives)

    # Reorder for batching: [Q1, Q3, Q2, Q4]
    # This allows Q1+Q3 (batch 1) and Q2+Q4 (batch 2) to run in parallel
    # since they're from different qubit pairs
    batched_order = [qubit_list[0], qubit_list[2], qubit_list[1], qubit_list[3]]
    qubits = QubitCollection(batched_order, batch_size=2)

    # Create the QUA program
    rabi_chevron_program = create_rabi_chevron_program_batched(
        machine=machine,
        qubits=qubits,
        n_avg=1,
        pulse_durations=[250],
        frequencies=[int(10e6)],
    )

    return machine, qubits, rabi_chevron_program


# =============================================================================
# SECTION 7: Cloud Simulator Execution
# =============================================================================

if __name__ == "__main__":
    print("Setting up Rabi Chevron experiment (batched version)...")

    machine, qubits, rabi_chevron_program = setup_rabi_chevron_experiment()

    # pylint: disable=unsubscriptable-object,no-member
    print(f"Machine configured with {len(machine.qubits)} qubit(s)")
    print(f"Qubits: {list(machine.qubits.keys())}")
    print(f"Quantum dot pairs: {list(machine.quantum_dot_pairs.keys())}")
    for q_name, q in machine.qubits.items():
        print(f"  {q_name}: dot={q.quantum_dot.id}, readout_dot={q.preferred_readout_quantum_dot}")
    print(f"Virtual gate sets: {list(machine.virtual_gate_sets.keys())}")
    # pylint: enable=unsubscriptable-object,no-member

    config = machine.generate_config()

    from configs import EMAIL, PASSWORD

    # Cloud Simulator Configuration
    # EMAIL = "email"
    # PASSWORD = "password"

    print("\nConnecting to QM SaaS cloud simulator...")
    client = qm_saas.QmSaas(
        email=EMAIL,
        password=PASSWORD,
        host="qm-saas.dev.quantum-machines.co",
    )
    print("Connected to QM SaaS cloud simulator...")

    client.close_all()

    with client.simulator(client.latest_version()) as instance:
        print("\nSimulating Rabi Chevron (batched)...")

        qmm = QuantumMachinesManager(
            host=instance.host,
            port=instance.port,
            connection_headers=instance.default_connection_headers,
        )

        simulation_config = SimulationConfig(duration=8000)
        job = qmm.simulate(config, rabi_chevron_program, simulation_config)
        job.wait_until("Done", timeout=10)

        simulated_samples = job.get_simulated_samples()
        waveform_report = job.get_simulated_waveform_report()

    waveform_report.create_plot(simulated_samples, plot=True)

    print("Retrieving simulated samples...")
    simulated_samples.con1.plot()
    plt.title("Rabi Chevron Experiment (Batched) - Simulated Waveforms")
    plt.tight_layout()
    plt.show()

    print("\nRabi Chevron simulation completed successfully!")
