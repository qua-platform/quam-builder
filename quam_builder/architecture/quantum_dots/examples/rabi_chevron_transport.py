"""
Rabi Chevron Experiment Example
===============================

This example demonstrates a complete Rabi chevron experiment workflow using the
QuAM quantum dots framework. A Rabi chevron experiment sweeps both drive frequency
and pulse duration to find the optimal qubit drive parameters, revealing the qubit's
resonance frequency and Rabi oscillation characteristics.

Readout in this example uses RF reflectometry: a resonator tone at 1 MHz
intermediate frequency is applied to the sensor resonator, and the reflected
signal is demodulated in the OPX using integration weights matched to the tone.

Workflow Overview:
------------------
1. **Create Machine**: Set up physical channels (plungers, sensor, drain, XY drive)
2. **Register Components**: Use register_channel_elements() and register_qubit()
3. **Define Macros**: Add drive() and measure() macros using the QuamMacro pattern
4. **Create QUA Program**: Build the experiment with voltage point navigation
5. **Run on Cloud Simulator**: Execute using QM SaaS

Key Concepts Demonstrated:
--------------------------
- VoltageGate channels with sticky mode for voltage sequences
- Virtual gate sets with cross-capacitance compensation
- Qubit registration with XY drive and sensor dot association
- Custom macros (DriveMacro, MeasureMacro) following the QuamMacro pattern
- RF reflectometry readout with a 1 MHz resonator tone
- Voltage point navigation using step_to_point()
- Cloud simulator execution via qm_saas

Requirements:
- Qubit with voltage points: init, operate, readout
- Drive macro for applying MW pulses with variable duration
- Measure macro returning demodulated transport current values
- Readout resonator connected to an LF output and input for reflectometry
- Voltage sequence with compensation pulse capability
"""

from typing import List

import matplotlib
import matplotlib.pyplot as plt
import qm_saas
from qm.qua import (
    program,
    for_,
    declare,
    declare_stream,
    fixed,
    update_frequency,
    align,
    assign,
    save,
    stream_processing,
)
from qm import SimulationConfig, QuantumMachinesManager
from quam.components import pulses
from quam.components.channels import StickyChannelAddon
from quam.components.ports import (
    LFFEMAnalogInputPort,
    LFFEMAnalogOutputPort,
    MWFEMAnalogOutputPort,
)
from quam.core import quam_dataclass
from quam.core.macro.quam_macro import QuamMacro

from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    XYDrive,
)
from quam_builder.architecture.quantum_dots.components.readout_resonator import (
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit


# =============================================================================
# SECTION 1: Create Machine and Physical Channels
# =============================================================================


def create_minimal_machine() -> LossDiVincenzoQuam:
    """
    Create a minimal machine configuration for the Rabi chevron experiment.

    This function sets up the hardware abstraction layer following the recommended
    pattern from quam_qd_example.py and quam_ld_example.py:

    1. Create physical VoltageGate channels (plungers + sensor DC)
    2. Create readout resonator channel for the sensor (RF reflectometry)
    3. Create XY drive channel for qubit control
    4. Create virtual gate set with cross-capacitance compensation
    5. Register all channel elements using register_channel_elements()
    6. Register quantum dot pairs to link dots with sensors

    Returns:
        Tuple of (machine, xy_drive, transport_readout)
    """
    machine = LossDiVincenzoQuam()

    # Define controller and FEM slots
    controller = "con1"
    lf_fem_slot = 2  # Low-frequency FEM for DC gates
    mw_fem_slot = 1  # Microwave FEM for XY drive

    # -------------------------------------------------------------------------
    # Physical Voltage Channels (Plunger Gates)
    # -------------------------------------------------------------------------
    # Sticky mode is required for VoltageSequence to maintain voltages between pulses
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

    # -------------------------------------------------------------------------
    # Sensor DC Channel
    # -------------------------------------------------------------------------
    # Dedicated VoltageGate for the sensor dot (DC bias only)
    sensor_dc = VoltageGate(
        id="sensor_DC",
        opx_output=LFFEMAnalogOutputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=4,
            output_mode="direct",
        ),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )

    # -------------------------------------------------------------------------
    # Readout Resonator (RF reflectometry at 1 MHz IF)
    # -------------------------------------------------------------------------
    readout_resonator = ReadoutResonatorSingle(
        id="sensor_resonator",
        opx_output=LFFEMAnalogOutputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=3,
            output_mode="direct",
        ),
        opx_input=LFFEMAnalogInputPort(
            controller_id=controller,
            fem_id=lf_fem_slot,
            port_id=1,
        ),
        intermediate_frequency=1e6,
        operations={
            "readout": pulses.SquareReadoutPulse(
                length=10000,
                amplitude=0.05,
                integration_weights_angle=0.0,
            )
        },
    )

    # -------------------------------------------------------------------------
    # XY Drive Channel
    # -------------------------------------------------------------------------
    # Microwave channel for qubit rotations
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
    # Add a variable-length drive pulse for Rabi experiments
    length = 100
    xy_drive.operations["drive"] = pulses.GaussianPulse(
        length=length,  # Default length in ns, will be overridden in experiment
        amplitude=0.2,
        sigma=length / 6,
    )

    # -------------------------------------------------------------------------
    # Virtual Gate Set
    # -------------------------------------------------------------------------
    # Maps virtual gates to physical channels with cross-capacitance compensation
    machine.create_virtual_gate_set(
        virtual_channel_mapping={
            "virtual_dot_1": plunger_1,
            "virtual_dot_2": plunger_2,
            "virtual_sensor_1": sensor_dc,
        },
        gate_set_id="main_qpu",
        # Compensation matrix (3x3) accounts for cross-capacitance between gates
        compensation_matrix=[
            [1.0, 0.1, 0.0],  # virtual_dot_1 -> physical channels
            [0.1, 1.0, 0.0],  # virtual_dot_2 -> physical channels
            [0.0, 0.0, 1.0],  # virtual_sensor_1 -> physical channels
        ],
    )

    # -------------------------------------------------------------------------
    # Register Channel Elements
    # -------------------------------------------------------------------------
    # This creates QuantumDot and SensorDot objects from the channels
    machine.register_channel_elements(
        plunger_channels=[plunger_1, plunger_2],
        sensor_readout_mappings={sensor_dc: readout_resonator},
        barrier_channels=[],
    )

    # -------------------------------------------------------------------------
    # Register Quantum Dot Pair
    # -------------------------------------------------------------------------
    # Links the quantum dots with the sensor dot for readout
    machine.register_quantum_dot_pair(
        quantum_dot_ids=["virtual_dot_1", "virtual_dot_2"],
        sensor_dot_ids=["virtual_sensor_1"],
        id="qd_pair_1_2",
    )

    return machine, xy_drive, readout_resonator


# =============================================================================
# SECTION 2: Register Qubit with Voltage Points
# =============================================================================


def register_qubit_with_points(
    machine: LossDiVincenzoQuam,
    xy_drive: XYDrive,
) -> LDQubit:
    """
    Register an LDQubit and define voltage points for the experiment.

    Voltage points define the gate voltage configurations for different stages
    of the experiment:
    - init: Load electron into the quantum dot
    - operate: Move to the manipulation sweet spot for driving
    - readout: Configure for Pauli spin blockade (PSB) readout

    Args:
        machine: The configured machine instance
        xy_drive: XY drive channel for qubit control

    Returns:
        LDQubit: The configured qubit instance with voltage points
    """
    # Register the qubit, linking it to a quantum dot and XY channel
    machine.register_qubit(
        qubit_name="Q1",
        quantum_dot_id="virtual_dot_1",
        xy_channel=xy_drive,
        readout_quantum_dot="virtual_dot_2",  # Partner dot for PSB readout
    )

    qubit = machine.qubits["Q1"]

    # -------------------------------------------------------------------------
    # Define Voltage Points using Fluent API
    # -------------------------------------------------------------------------
    # Note: All durations must be multiples of 4ns (OPX clock cycles)
    (
        qubit
        # Init point: Load electron into dot at low voltage
        .with_step_point(
            name="init",
            voltages={"virtual_dot_1": 0.05},
            duration=500,  # 500ns hold time
        )
        # Operate point: Move to manipulation sweet spot
        .with_step_point(
            name="operate",
            voltages={"virtual_dot_1": 0.15},
            duration=2000,  # 2us hold time (will be overridden by drive duration)
        )
        # Readout point: Configure for PSB readout
        .with_step_point(
            name="readout",
            voltages={"virtual_dot_1": -0.05, "virtual_sensor_1": 0.1},
            duration=2000,  # 2us readout window
        )
    )

    return qubit


# =============================================================================
# SECTION 3: Define Custom Macros (Drive and Measure)
# =============================================================================


def add_qubit_macros(qubit: LDQubit):
    """
    Add drive and measure macros to the qubit using the QuamMacro pattern.

    This follows the recommended approach from macro_examples.py where macros
    are defined as QuamMacro subclasses and registered in qubit.macros. This
    allows them to be called as methods (e.g., qubit.drive(duration=t)).

    Macros defined:
    - DriveMacro: Applies MW pulse with optional duration override (for Rabi sweep)
    - MeasureMacro: Performs measurement and returns R^2

    The sensor_dot is accessed through qubit.sensor_dots[0], following the pattern:
        machine.qubits["Q1"].sensor_dots[0].physical_channel.readout.measure("readout")

    Args:
        qubit: The qubit to enhance with macros
    """

    # -------------------------------------------------------------------------
    # Drive Macro
    # -------------------------------------------------------------------------
    @quam_dataclass
    class DriveMacro(QuamMacro):  # pylint: disable=too-few-public-methods
        """
        Macro for applying a microwave drive pulse with variable duration.

        This macro is essential for Rabi chevron experiments where the drive
        duration is swept as an experimental parameter. The duration can be
        overridden at call time via kwargs.

        Attributes:
            pulse_name: Name of the pulse operation to play (default: "drive")
            amplitude_scale: Optional amplitude scaling factor
        """

        pulse_name: str = "drive"
        amplitude_scale: float = None

        def apply(self, **kwargs):
            """
            Apply a microwave drive pulse to the qubit's XY channel.

            Args (via kwargs):
                duration: Pulse duration in clock cycles (4ns each). If None, uses default.
                amplitude_scale: Optional amplitude scaling factor
            """
            duration = kwargs.get("duration", None)
            amp_scale = kwargs.get("amplitude_scale", self.amplitude_scale)

            # Navigate to the qubit: self.parent is the macros dict, parent.parent is the qubit
            parent_qubit = self.parent.parent

            if parent_qubit.xy_channel is None:
                raise ValueError(f"No XY channel configured for qubit {parent_qubit.id}")

            parent_qubit.xy_channel.play(
                self.pulse_name,
                amplitude_scale=amp_scale,
                duration=duration,
            )

    # Register the drive macro
    drive_macro = DriveMacro(pulse_name="drive")
    qubit.macros["drive"] = drive_macro

    # -------------------------------------------------------------------------
    # Measure Macro
    # -------------------------------------------------------------------------
    @quam_dataclass
    class MeasureMacro(QuamMacro):  # pylint: disable=too-few-public-methods
        """
        Macro for performing resonator readout and returning R^2.

        This macro accesses the sensor dot through the qubit's sensor_dots
        property, which is populated when the quantum dot pair is registered.

        Attributes:
            pulse_name: Name of the readout pulse operation (default: "readout")
        """

        pulse_name: str = "readout"

        def apply(self, **kwargs):
            """
            Perform demodulated resonator measurement and return R^2.

            Returns:
                R^2 QUA variable containing measurement result
            """
            pulse = kwargs.get("pulse_name", self.pulse_name)

            # Declare QUA variables for I/Q and R^2
            I = declare(fixed)
            Q = declare(fixed)
            r2 = declare(fixed)

            # Navigate to qubit and get the associated sensor dot
            parent_qubit = self.parent.parent
            sensor_dot = parent_qubit.sensor_dots[0]

            resonator = sensor_dot.readout_resonator

            # Wait for transients, then perform demodulated measurement
            resonator.wait(64)
            resonator.measure(pulse, qua_vars=(I, Q))
            assign(r2, I * I + Q * Q)

            return r2

    # Register the measure macro
    measure_macro = MeasureMacro(pulse_name="readout")
    qubit.macros["measure"] = measure_macro


# =============================================================================
# SECTION 4: Create the Rabi Chevron QUA Program
# =============================================================================


def create_rabi_chevron_program(qubits: List[LDQubit]):
    """
    Create the Rabi chevron QUA program that sweeps frequency and duration.

    The program structure:
    1. Loop over averages (Navg)
    2. Loop over drive durations (t_ini to t_final)
    3. Loop over drive frequencies (f_ini to f_final)
    4. For each point: init -> operate (with drive) -> readout -> compensate

    Args:
        qubits: List of qubits to run the experiment on

    Returns:
        QUA program for the Rabi chevron experiment
    """
    # Experiment parameters
    Navg = 1  # Number of averages
    t_wait = 64  # clock cycles
    t_ini = 50  # Initial duration (clock cycles, 1 cycle = 4ns)
    t_final = 350  # Final duration (clock cycles)
    dt = 100  # Duration step (clock cycles)
    f_ini = int(10e3)  # Initial frequency (Hz)
    f_final = int(30e6)  # Final frequency (Hz)
    df = int(10e6)  # Frequency step (Hz)

    with program() as rabi_chevron:
        # Declare QUA variables
        n = declare(int)  # Averaging counter
        t = declare(int)  # Drive duration (clock cycles)
        f = declare(int)  # Drive frequency (Hz)

        # Declare streams for data acquisition
        current_stream = declare_stream()

        for qubit in qubits:
            with for_(n, 0, n < Navg, n + 1):
                with for_(t, t_ini, t < t_final, t + dt):
                    with for_(f, f_ini, f < f_final, f + df):
                        # Set the drive frequency for this iteration
                        update_frequency(qubit.xy_channel.name, f)

                        # Step 1: Initialize - load electron into dot
                        qubit.step_to_point("init")

                        # Synchronize all elements before operation
                        align()

                        # Step 2: Operate - move to sweet spot and apply drive
                        # Duration is extended to accommodate the drive pulse
                        qubit.step_to_point("operate", duration=4 * (t + t_wait))

                        # Apply the microwave drive pulse with variable duration
                        qubit.drive(duration=t)

                        # Synchronize before readout
                        align()

                        # Step 3: Readout - move to PSB configuration and measure
                        qubit.step_to_point("readout")
                        current = qubit.measure()
                        save(current, current_stream)

                        align()

                        # Step 4: Apply compensation pulse to reset DC bias
                        qubit.voltage_sequence.apply_compensation_pulse()

        # Stream processing: reshape data into 2D arrays
        with stream_processing():
            current_stream.buffer(
                (f_final - f_ini) // df,
                (t_final - t_ini) // dt,
            ).average().save("current")

    return rabi_chevron


# =============================================================================
# SECTION 5: Main Entry Point and Experiment Setup
# =============================================================================


def setup_rabi_chevron_experiment():
    """
    Set up all components needed for the Rabi chevron experiment.

    This orchestrates the full setup:
    1. Create the machine with all hardware channels
    2. Register the qubit with voltage points
    3. Add drive and measure macros
    4. Create the QUA program

    Returns:
        Tuple of (machine, qubits, rabi_chevron_program)
    """
    # Create machine with physical channels
    machine, xy_drive, readout_resonator = create_minimal_machine()

    # Register qubit with voltage points
    qubit = register_qubit_with_points(machine, xy_drive)

    # Add drive and measure macros to the qubit
    add_qubit_macros(qubit)

    # Create list of qubits for the experiment
    qubits = [qubit]

    # Create the QUA program
    rabi_chevron_program = create_rabi_chevron_program(qubits)

    return machine, qubits, rabi_chevron_program


# =============================================================================
# SECTION 6: Cloud Simulator Execution
# =============================================================================

if __name__ == "__main__":
    print("Setting up Rabi Chevron experiment...")

    # Set up the experiment
    machine, qubits, rabi_chevron_program = setup_rabi_chevron_experiment()

    # Display configuration summary
    # pylint: disable=unsubscriptable-object,no-member
    print(f"Machine configured with {len(machine.qubits)} qubit(s)")
    print(f"Qubit Q1 has macros: {list(machine.qubits['Q1'].macros.keys())}")
    print(f"Virtual gate sets: {list(machine.virtual_gate_sets.keys())}")
    print(f"Quantum dots: {list(machine.quantum_dots.keys())}")
    # pylint: enable=unsubscriptable-object,no-member

    # Generate the QUA config from the machine
    config = machine.generate_config()

    # -------------------------------------------------------------------------
    # Cloud Simulator Configuration (QM SaaS Dev Server)
    # -------------------------------------------------------------------------
    # EMAIL = "email"
    # PASSWORD = "password"
    from configs import EMAIL, PASSWORD

    print("\nConnecting to QM SaaS cloud simulator...")
    client = qm_saas.QmSaas(
        email=EMAIL,
        password=PASSWORD,
        host="qm-saas.dev.quantum-machines.co",
    )
    print("Connected to QM SaaS cloud simulator...")

    # Close any stale instances (limit is 3 per user)
    client.close_all()

    # Run simulation using context manager (auto-closes instance on exit)
    with client.simulator(client.latest_version()) as instance:
        print("\nSimulating Rabi Chevron...")

        # Create QuantumMachinesManager connected to the cloud instance
        qmm = QuantumMachinesManager(
            host=instance.host,
            port=instance.port,
            connection_headers=instance.default_connection_headers,
        )

        # Run the simulation
        simulation_config = SimulationConfig(duration=8000)
        job = qmm.simulate(config, rabi_chevron_program, simulation_config)
        job.wait_until("Done", timeout=10)

        # Retrieve results
        simulated_samples = job.get_simulated_samples()
        waveform_report = job.get_simulated_waveform_report()

    # Run the simulation
    # qmm = QuantumMachinesManager(host="172.16.33.114", cluster_name="CS_4")
    # simulation_config = SimulationConfig(duration=4000)
    # job = qmm.simulate(config, rabi_chevron_program, simulation_config)
    # job.wait_until("Done", timeout=20)
    #
    # # Retrieve results
    # simulated_samples = job.get_simulated_samples()
    # waveform_report = job.get_simulated_waveform_report()

    # Plot the results
    import matplotlib

    matplotlib.use("TkAgg")
    waveform_report.create_plot(simulated_samples, plot=True)

    print("Retrieving simulated samples...")
    simulated_samples.con1.plot()
    plt.title("Rabi Chevron Transport Experiment - Simulated Waveforms")
    plt.tight_layout()
    plt.show()

    print("\nRabi Chevron simulation completed successfully!")

    # qmm.close_all_qms()
