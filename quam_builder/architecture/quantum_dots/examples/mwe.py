# ruff: noqa
"""
Demonstration of qubit.align() behavior within simultaneous() blocks.

This example investigates how qubit.align() interacts with the
voltage_sequence.simultaneous() context when executing operations on multiple qubits.

Key concepts demonstrated:
1. Simple voltage macros (step to points)
2. Pulse macros (x180 as square pulse)
3. Interaction between qubit.align() and simultaneous()
4. Multiplexed readout pattern with alignment
"""

# ============================================================================
# Imports
# ============================================================================
from qm import qua
from qm.qua import *
from quam.components import StickyChannelAddon, pulses
from quam.components.macro import PulseMacro
from quam.components.ports import LFFEMAnalogInputPort, LFFEMAnalogOutputPort, MWFEMAnalogOutputPort
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorSingle, VoltageGate
from quam_builder.architecture.quantum_dots.components.xy_drive import XYDrive
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.tools.macros import MeasureMacro

# ============================================================================
# Machine Setup
# ============================================================================

# Initialize machine
machine = BaseQuamQD()

# Hardware configuration parameters
n_qubits = 2
lf_fem_dots = 1
lf_fem_resonators = 2
mw_fem_dots = 5


import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

plt.plot([1, 2, 3])
plt.show()


# ============================================================================
# Physical Channels - Voltage Gates
# ============================================================================

# Create plunger gates with sticky voltage
j = 1
plunger_gates = [
    VoltageGate(
        id=f"plunger_{i}",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem_dots, port_id=i + j),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    for i in range(n_qubits)
]
j += n_qubits

# Create barrier gates with sticky voltage
barrier_gates = [
    VoltageGate(
        id=f"barrier_{i}",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem_dots, port_id=i + j),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    for i in range(n_qubits - 1)
]
j += n_qubits - 1

# Create sensor gates for readout (only 1 shared sensor gate for multiplexed readout)
sensor_gates = [
    VoltageGate(
        id="sensor_0",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem_dots, port_id=j + 1),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
]

# ============================================================================
# Readout Resonators
# ============================================================================

# Create only 1 readout resonator (shared for multiplexed readout of both qubits)
readout_resonators = [
    ReadoutResonatorSingle(
        id="readout_resonator_0",
        frequency_bare=5.0e9,  # 5 GHz
        intermediate_frequency=50e6,  # 50 MHz IF
        operations={
            "readout": pulses.SquareReadoutPulse(
                length=240,  # ns
                id="readout",
                amplitude=0.12,
            )
        },
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem_resonators, port_id=1),  # Output port 1
        opx_input=LFFEMAnalogInputPort("con1", lf_fem_resonators, port_id=1),  # Input port 1
    )
]

# ============================================================================
# Virtual Gate Set
# ============================================================================

machine.create_virtual_gate_set(
    virtual_channel_mapping={
        **{f"virtual_dot_{i}": plunger_gates[i] for i in range(n_qubits)},
        **{f"virtual_barrier_{i}": barrier_gates[i] for i in range(n_qubits - 1)},
        "virtual_sensor_0": sensor_gates[0],  # Single shared sensor
    },
    gate_set_id="main_qpu",
    allow_rectangular_matrices=True,
)

# ============================================================================
# Register Components
# ============================================================================

# Register the shared sensor gate with shared resonator
machine.register_channel_elements(
    plunger_channels=plunger_gates,
    barrier_channels=barrier_gates,
    sensor_channels_resonators=[(sensor_gates[0], readout_resonators[0])],
)

# ============================================================================
# Register Qubits
# ============================================================================

# Register qubits as LDQubits individually
for i in range(n_qubits):
    machine.register_qubit(
        qubit_type="loss_divincenzo",
        quantum_dot_id=f"virtual_dot_{i}",
        id=f"Q{i}",
        xy_channel=XYDrive(
            id=f"Q{i}_xy",
            opx_output=MWFEMAnalogOutputPort(
                "con1",
                mw_fem_dots,
                port_id=i + 1,
                upconverter_frequency=5e9,
                band=2,
                full_scale_power_dbm=10,
            ),
            intermediate_frequency=10e6,
        ),
    )

# ============================================================================
# Configure Voltage Points and Operations
# ============================================================================

# Voltage configuration: simple step points for each operation
VOLTAGE_CONFIG_0 = {
    "initialize": {
        "virtual_dot_0": -0.15,
    },
    "operate": {
        "virtual_dot_0": 0.0,
    },
    "measure": {
        "virtual_dot_0": 0.15,
    },
}
VOLTAGE_CONFIG_1 = {
    "initialize": {
        "virtual_dot_1": -0.3,
    },
    "operate": {
        "virtual_dot_1": 0.0,
    },
    "measure": {
        "virtual_dot_1": 0.3,
    },
}


# Pulse configuration
PULSE_CONFIG = {
    "x180": {
        "amplitude": 0.25,
        "length": 120,  # ns
    }
}

# Timing configuration
TIMING_CONFIG = {
    "initialize_hold": 200,  # ns
    "operate_hold": 400,  # ns
    "measure_hold": 480,  # ns
    "reset_wait_time": 25,  # cycles (100 ns)
}

machine.sensor_dots["virtual_sensor_0"].readout_resonator.time_of_flight = 32


def configure_qubit_operations(qubit, qubit_index, VOLTAGE_CONFIG):
    """
    Configure a qubit with voltage points, pulse macros, and utility macros.

    Args:
        qubit: The LDQubit instance to configure
        qubit_index: Index of the qubit (0, 1, 2, ...)
    """
    # === VOLTAGE POINT MACROS (Step Points) ===
    # Using fluent API to define voltage points
    qubit.with_step_point(
        "initialize_point",
        {f"virtual_dot_{qubit_index}": VOLTAGE_CONFIG["initialize"][f"virtual_dot_{qubit_index}"]},
        hold_duration=TIMING_CONFIG["initialize_hold"],
    )

    qubit.with_step_point(
        "operate_point",
        {f"virtual_dot_{qubit_index}": VOLTAGE_CONFIG["operate"][f"virtual_dot_{qubit_index}"]},
        hold_duration=TIMING_CONFIG["operate_hold"],
    )

    qubit.with_step_point(
        "measure_point",
        {f"virtual_dot_{qubit_index}": VOLTAGE_CONFIG["measure"][f"virtual_dot_{qubit_index}"]},
        hold_duration=TIMING_CONFIG["measure_hold"],
    )

    # === PULSE MACROS (Square Pulses) ===
    # Add x180 pulse to xy_channel
    qubit.xy_channel.operations["x180"] = pulses.SquarePulse(
        amplitude=PULSE_CONFIG["x180"]["amplitude"], length=PULSE_CONFIG["x180"]["length"]
    )

    # Create pulse macro for x180
    qubit.macros["x180"] = PulseMacro(pulse=qubit.xy_channel.operations["x180"].get_reference())

    # === UTILITY MACROS ===
    # Measurement macro - access shared sensor dot via machine
    sensor_dot = machine.sensor_dots["virtual_sensor_0"]  # Shared sensor for all qubits
    qubit.macros["measure"] = MeasureMacro(
        threshold=0.05, component=sensor_dot.readout_resonator.get_reference()
    )

    # Note: align() and wait() are built-in methods on the qubit object,
    # so we don't need to define them as macros

    # === COMPOSITE SEQUENCES (Using Fluent API) ===
    qubit.with_sequence("initialize", ["initialize_point"])
    qubit.with_sequence(
        "full_cycle", ["initialize_point", "operate_point", "x180", "measure_point"]
    )


# Configure all qubits
for i, (qubit, VOLTAGE_CONFIG) in enumerate(
    zip(machine.qubits.values(), [VOLTAGE_CONFIG_0, VOLTAGE_CONFIG_1], strict=False)
):
    configure_qubit_operations(qubit, i, VOLTAGE_CONFIG)

with program() as prog_basic:
    """
    This demonstrates the fundamental interaction:
    - simultaneous() ensures all voltage operations happen in parallel
    - align() synchronizes timing between operations within each qubit
    """

    # Declare measurement variables
    state_e = declare(bool)
    state_e_st = declare_stream()
    for qubit in machine.qubits.values():
        qua.align()
        # Step 1: Initialize to ground state
        qubit.initialize_point()
        # Align 1: Wait for all qubits to finish initialization
        qubit.align()
        qubit.operate_point()
        # Step 2: Apply X180 pulse
        qubit.x180()
        # Align 2: Wait for all qubits to finish X180
        qubit.align()
        # Step 3: Measure (returns discriminated state)
        qubit.measure_point()
        state = qubit.measure()

    qua.wait(100)

    qubit.voltage_sequence.ramp_to_zero()

    # Save results
    save(state_e, state_e_st)

    with stream_processing():
        state_e_st.save("state_e")

with program() as prog_sim:
    """
    This demonstrates the fundamental interaction:
    - simultaneous() ensures all voltage operations happen in parallel
    - align() synchronizes timing between operations within each qubit
    """
    channels = []
    for qubit in machine.qubits.values():
        channels.extend([ch.name for ch in qubit.channels.values()])
    # Declare measurement variables
    state_e = declare(bool)
    state_e_st = declare_stream()
    with machine.get_voltage_sequence("main_qpu").simultaneous(duration=200):
        for qubit in machine.qubits.values():
            qubit.initialize_point()

    with machine.get_voltage_sequence("main_qpu").simultaneous(duration=200):
        for qubit in machine.qubits.values():
            qubit.operate_point()

    for qubit in machine.qubits.values():
        # Step 2: Apply X180 pulse
        qubit.x180()

    qua.align(*channels)

    with machine.get_voltage_sequence("main_qpu").simultaneous(duration=200):
        for qubit in machine.qubits.values():
            qubit.measure_point()

    qua.align(*channels)
    qubit.measure()
    qua.wait(100)

    qubit.voltage_sequence.ramp_to_zero()

    # Save results
    save(state_e, state_e_st)

    with stream_processing():
        state_e_st.save("state_e")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Running simulation...")
    print("=" * 80)

    import matplotlib
    from qm_saas import QmSaas

    from qm import QuantumMachinesManager, SimulationConfig

    # matplotlib.use("TkAgg")

    print("Attempting to connect to QmSaas simulator...")
    client = QmSaas(
        email="Sebastian.Orbell@quantum-machines.co",
        password="mugzoc-juFgez-matbe5",
        host="qm-saas.dev.quantum-machines.co",
    )

    with client.simulator(client.latest_version()) as instance:
        # Use the instance object to simulate QUA programs
        qmm = QuantumMachinesManager(
            host=instance.host,
            port=instance.port,
            connection_headers=instance.default_connection_headers,
        )

        # Continue as usual with opening a quantum machine and simulation of a qua program
        simulation_config = SimulationConfig(duration=4_000 // 4)  # In clock cycles = 4ns
        # Simulate blocks python until the simulation is done

        config = machine.generate_config()
        prog = prog_sim
        job = qmm.simulate(config, prog, simulation_config)
        # Get the simulated samples
        samples = job.get_simulated_samples()
        # Plot the simulated samples
        samples.con1.plot()
        # Get the waveform report object
        waveform_report = job.get_simulated_waveform_report()
        # Cast the waveform report to a python dictionary
        waveform_dict = waveform_report.to_dict()
        # Visualize and save the waveform report
        waveform_report.create_plot(samples, plot=True)
        print("✓ Simulation completed successfully!")

# %%
