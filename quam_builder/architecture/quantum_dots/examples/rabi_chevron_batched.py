"""
Rabi Chevron Experiment Example - Batched Qubits Version
=========================================================

This example demonstrates a Rabi chevron experiment using the batched qubits pattern
with integrated initialize and measure macros. This version follows the node-based
workflow pattern:

    with program() as node.namespace["qua_program"]:
        p1, p2, pdiff, p1_st, p2_st, pdiff_st, n, n_st = node.machine.declare_qua_variables()

Key Features:
-------------
- Uses `node.machine.declare_qua_variables()` pattern
- `InitializeMacro`: Steps to 'init' point to load electron
- `X180Macro`: Steps to 'operate' point and applies X180 (pi) pulse
- `MeasureMacro`: Steps to 'readout' point, measures I/Q, applies projector and threshold

Thresholding with Projector:
----------------------------
The MeasureMacro uses the sensor_dot's calibrated projector and threshold:
    projected = wI * I + wQ * Q + offset
    state = projected > threshold

This allows for arbitrary rotation of the I/Q plane to align with the measurement
axis and apply appropriate thresholding for parity readout.

Workflow Overview:
------------------
1. Pre-measure: Get initial state p1 (for comparison)
2. Initialize: Step to init point and load electron
3. X180: Step to operate point and apply pi pulse with variable duration
4. Measure: Step to readout point, measure, threshold → parity p2
5. Compensate: Apply compensation pulse to reset DC bias
6. Save: p1, p2, and pdiff (state difference)
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
class InitializeMacro(QuamMacro):  # pylint: disable=too-few-public-methods
    """Macro for qubit initialization including voltage point navigation.

    This macro:
    1. Steps to the 'init' voltage point
    2. Holds for specified duration to load electron into dot

    The duration can be overridden at call time for Rabi experiments
    where longer initialization may be needed.

    Attributes:
        default_duration: Default hold duration at initialize point (ns)
    """

    duration: int = 500

    def apply(self, duration: int = None, **kwargs) -> None:
        """Execute initialization sequence.

        Args:
            duration: Override for hold duration at init point (ns)
        """
        hold_duration = duration if duration is not None else self.duration

        # Navigate to the qubit: self.parent is macros dict, parent.parent is qubit
        parent_qubit = self.parent.parent

        # Step to initialization point
        parent_qubit.step_to_point("initialize", duration=hold_duration)


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

    def apply(self, duration: int = None, **kwargs) -> None:
        """Execute X180 gate sequence.

        Args:
            duration: Pulse duration in clock cycles (4ns each)
        """
        parent_qubit = self.parent.parent

        # Apply X180 pulse if duration specified
        if duration is not None and parent_qubit.xy_channel is not None:
            amp_scale = kwargs.get("amplitude_scale", self.amplitude_scale)
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
    3. Applies projector: projected = wI * I + wQ * Q + offset
    4. Thresholds to get parity: state = projected > threshold

    The projector and threshold are retrieved from the sensor_dot's
    readout_projectors and readout_thresholds dictionaries, keyed by
    the quantum_dot_pair_id.

    Attributes:
        pulse_name: Name of the readout pulse operation (default: "readout")
        readout_duration: Hold duration at readout point (ns)
    """

    pulse_name: str = "readout"
    readout_duration: int = 2000

    def apply(self, **kwargs) -> QuaVariableBool:
        """Execute measurement sequence and return qubit state (parity).

        The measurement uses the sensor_dot's calibrated projector (wI, wQ, offset)
        and threshold to convert I/Q values to a boolean parity result.

        Returns:
            Boolean QUA variable indicating qubit state (True = excited/odd parity)
        """
        pulse = kwargs.get("pulse_name", self.pulse_name)

        # Navigate to qubit
        parent_qubit = self.parent.parent

        # Step to readout point (PSB configuration) - integrated into measure
        parent_qubit.step_to_point("readout", duration=self.readout_duration)

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

        # Get projector and threshold from sensor_dot (with defaults)
        projector = sensor_dot.readout_projectors.get(
            qd_pair_id, {"wI": 1.0, "wQ": 0.0, "offset": 0.0}
        )
        threshold = sensor_dot.readout_thresholds.get(qd_pair_id, 0.0)

        wI = projector.get("wI", 1.0)
        wQ = projector.get("wQ", 0.0)
        offset = projector.get("offset", 0.0)

        # Apply projector: projected = wI * I + wQ * Q + offset
        projected = declare(fixed)
        assign(projected, wI * I + wQ * Q + offset)

        # Threshold to get parity state
        state = declare(bool)
        assign(state, projected > threshold)

        return state


# =============================================================================
# SECTION 2: Qubit Collection for Batching
# =============================================================================


@dataclass
class QubitBatch:  # pylint: disable=too-few-public-methods
    """Container for a batch of qubits with indexed access.

    Provides iteration over qubits with index tracking for use in
    batched QUA programs where results need to be saved per-qubit.
    """

    qubits: List[LDQubit]

    def items(self):
        """Iterate over (index, qubit) pairs."""
        return enumerate(self.qubits)

    def __len__(self):
        return len(self.qubits)


class QubitCollection:  # pylint: disable=too-few-public-methods
    """Collection of qubits supporting batched execution.

    Provides a batch() method that yields QubitBatch objects for
    iteration in QUA programs. Currently configured for batch_size=1.
    """

    def __init__(self, qubits: List[LDQubit], batch_size: int = 1):
        self.qubits = qubits
        self.batch_size = batch_size

    def batch(self):
        """Yield batches of qubits.

        Currently yields single-qubit batches to simplify initial implementation.
        """
        for i in range(0, len(self.qubits), self.batch_size):
            yield QubitBatch(self.qubits[i : i + self.batch_size])


# =============================================================================
# SECTION 3: Create Machine and Physical Channels
# =============================================================================


def create_minimal_machine() -> LossDiVincenzoQuam:
    """Create a minimal machine configuration for the Rabi chevron experiment."""
    # pylint: disable=unexpected-keyword-arg
    # Note: pylint doesn't understand quam_dataclass dynamic constructors
    machine = LossDiVincenzoQuam()

    controller = "con1"
    lf_fem_slot = 2
    mw_fem_slot = 1

    # Physical Voltage Channels
    plunger_1 = VoltageGate(
        id="plunger_1",
        opx_output=LFFEMAnalogOutputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=1,
            output_mode="direct",
        ),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

    plunger_2 = VoltageGate(
        id="plunger_2",
        opx_output=LFFEMAnalogOutputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=2,
            output_mode="direct",
        ),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

    sensor_dc = VoltageGate(
        id="sensor_DC",
        opx_output=LFFEMAnalogOutputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=5,
            output_mode="direct",
        ),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

    # Readout Resonator (IQ)
    readout_resonator = ReadoutResonatorIQ(
        id="sensor_resonator",
        opx_output_I=LFFEMAnalogOutputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=3,
            output_mode="direct",
        ),
        opx_output_Q=LFFEMAnalogOutputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=4,
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
    )

    # XY Drive Channel
    xy_drive = XYDrive(
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

    length = 100
    xy_drive.operations["X180"] = pulses.GaussianPulse(
        length=length, amplitude=0.2, sigma=length / 6
    )

    # Virtual Gate Set
    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": plunger_1,
            "virtual_dot_2": plunger_2,
            "virtual_sensor_1": sensor_dc,
        },
        gate_set_id="main_qpu",
        compensation_matrix=[
            [1.0, 0.1, 0.0],
            [0.1, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
    )

    # Register Channel Elements
    machine.register_channel_elements(
        plunger_channels=[plunger_1, plunger_2],
        sensor_resonator_mappings={sensor_dc: readout_resonator},
        barrier_channels=[],
    )

    # Register Quantum Dot Pair
    machine.register_quantum_dot_pair(
        quantum_dot_ids=["virtual_dot_1", "virtual_dot_2"],
        sensor_dot_ids=["virtual_sensor_1"],
        id="qd_pair_1_2",
    )

    # Configure readout threshold and projector for the sensor dot
    # The projector rotates I/Q to align with the measurement axis:
    #   projected = wI * I + wQ * Q + offset
    # The threshold determines state discrimination:
    #   state = projected > threshold
    sensor_dot = machine.sensor_dots["virtual_sensor_1"]  # pylint: disable=unsubscriptable-object
    sensor_dot._add_readout_params(
        quantum_dot_pair_id="qd_pair_1_2",
        threshold=0.0,  # Threshold for parity discrimination
        projector={
            "wI": 1.0,  # Weight for I quadrature
            "wQ": 0.0,  # Weight for Q quadrature
            "offset": 0.0,  # DC offset correction
        },
    )

    return machine, xy_drive, readout_resonator


# =============================================================================
# SECTION 4: Register Qubit with Voltage Points and Macros
# =============================================================================


def register_qubit_with_points(
    machine: LossDiVincenzoQuam,
    xy_drive: XYDrive,
) -> LDQubit:
    """Register an LDQubit with voltage points and custom macros."""

    machine.register_qubit(
        qubit_name="Q1",
        quantum_dot_id="virtual_dot_1",
        xy_channel=xy_drive,
        readout_quantum_dot="virtual_dot_2",
    )

    qubit = machine.qubits["Q1"]

    # Define Voltage Points
    (
        qubit.with_step_point(
            name="initialize",
            voltages={"virtual_dot_1": 0.05},
            point_duration=500,
        )
        .with_step_point(
            name="operate",
            voltages={"virtual_dot_1": 0.15},
            point_duration=2000,
        )
        .with_step_point(
            name="readout",
            voltages={"virtual_dot_1": -0.05},
            point_duration=2000,
        )
    )

    # Register custom macros
    # qubit.macros["initialize"] = InitializeMacro(default_duration=500)
    qubit.macros["x180"] = X180Macro(pulse_name="X180")
    qubit.macros["measure"] = MeasureMacro(
        pulse_name="readout",
        readout_duration=2000,
    )

    return qubit


# =============================================================================
# SECTION 5: Create the Rabi Chevron QUA Program (Batched Version)
# =============================================================================


def create_rabi_chevron_program_batched(
    machine: LossDiVincenzoQuam,
    qubits: QubitCollection,
    n_avg: int = 1,
    pulse_durations: List[int] = None,
    frequencies: List[int] = None,
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
        pulse_durations = [50, 150, 250, 350]  # clock cycles (4ns each)
    if frequencies is None:
        frequencies = [int(10e3), int(10e6), int(20e6), int(30e6)]  # Hz

    num_qubits = len(qubits.qubits)

    with program() as rabi_chevron:
        # Declare QUA variables using machine's method
        # Returns: (I_list, I_st_list, Q_list, Q_st_list, n, n_st)
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables(num_IQ_pairs=num_qubits)

        # Additional variables for pre/post measurement comparison
        # Use int instead of bool so we can average in stream processing
        p1 = [declare(int) for _ in range(num_qubits)]
        p2 = [declare(int) for _ in range(num_qubits)]
        pdiff = [declare(int) for _ in range(num_qubits)]

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
                            # Measure initial state (includes step_to('readout'))
                            # Cast bool to int for stream averaging
                            assign(p1[i], Cast.to_int(qubit.measure()))

                            # Set drive frequency for this iteration
                            update_frequency(qubit.xy_channel.name, frequency)

                        # ---------------------------------------------------------
                        # Step 1: Initialize - load electron into dot
                        # ---------------------------------------------------------
                        for i, qubit in batched_qubits.items():
                            # Initialize with duration scaled to pulse_duration
                            qubit.initialize(duration=4 * (pulse_duration + 40))

                        # Synchronize before operation
                        align()

                        # ---------------------------------------------------------
                        # Step 2: X180 - move to sweet spot and apply pi pulse
                        # ---------------------------------------------------------
                        for i, qubit in batched_qubits.items():
                            # X180 macro handles step_to('operate') + X180 pulse
                            qubit.x180(duration=pulse_duration)

                        # Synchronize before measurement
                        align()

                        # ---------------------------------------------------------
                        # Step 3: Measure - move to PSB and measure
                        # ---------------------------------------------------------
                        for i, qubit in batched_qubits.items():
                            # Measure macro handles step_to('readout') + measurement
                            # Cast bool to int for stream averaging
                            assign(p2[i], Cast.to_int(qubit.measure()))

                        # Synchronize before compensation
                        align()

                        # ---------------------------------------------------------
                        # Step 4: Apply compensation pulse to reset DC bias
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
    """Set up all components for the Rabi chevron experiment."""

    # Create machine
    machine, xy_drive, readout_resonator = create_minimal_machine()

    # Register qubit with voltage points and macros
    qubit = register_qubit_with_points(machine, xy_drive)

    # Create qubit collection (batch_size=1 for now)
    qubits = QubitCollection([qubit], batch_size=1)

    # Create the QUA program
    rabi_chevron_program = create_rabi_chevron_program_batched(
        machine=machine,
        qubits=qubits,
        n_avg=1,
        pulse_durations=[50, 150, 250, 350],
        frequencies=[int(10e3), int(10e6), int(20e6), int(30e6)],
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
    print(f"Qubit Q1 has macros: {list(machine.qubits['Q1'].macros.keys())}")
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
