"""

This is an example script on how to instantiate a QPU which contains Loss-DiVincenzo qubits, with other barrier gates and sensor dots. 

Workflow: 

1. Instantiate the base components for the machine. This includes: 
    - QuantumDots (with their associated VoltageGate channels)
    - Barrier Gates (A thin wrapper around VoltageGate) - if this is not attached to a LDQubitPair, this will not be included in the machine
    - Sensor Dots (with the relevant readout resonator information)

2. Instantiate your qubits using te existing QuantumDot objects.
    - Either ensure that the qubit ids match those of the QuantumDots, or leave blank

3. Instantiate your machine. 

4. Add the qubits to your machine. 
    - The qubits must be added to the machine before they are added to the LDQubitPair, for parenting reasons

5. Create any relevant LDQubitPair objects
    - The machine will still be able to instantiate and use the qubits; however, without the addition of QubitPairs, 
        the sensors and barrier gates are not necessarily added. 

6. Create the QPU VirtualGateSet
    - Done through the command Quam.create_virtual_gate_set()

"""

from quam.components import (
    StickyChannelAddon, 
    InOutSingleChannel, 
    DigitalOutputChannel
) 
from quam.components.ports import (
    FEMPortsContainer,
    LFFEMAnalogOutputPort,      # Concrete implementation
    MWFEMAnalogOutputPort,      # Concrete implementation
    MWFEMAnalogInputPort,       # Concrete implementation
    FEMDigitalOutputPort,       # Concrete implementation
)

from quam_builder.architecture.quantum_dots.components import QuantumDot, VoltageGate, SensorDot, BarrierGate
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorMW


machine = BaseQuamQD()


lf_fem = 6
mw_fem = 1
# Set up the channels arbitrarily

plungers = [
    VoltageGate(
        id = f"plunger_{i}",
        opx_output = LFFEMAnalogOutputPort(
            "con1",
            lf_fem,
            port_id = i, 
        ), 
        sticky = StickyChannelAddon(duration = 16, digital = False), 
    )
    for i in [1, 2, 3, 4]
]

barriers = [
    VoltageGate(
        id = f"barrier_{i}",
        opx_output = LFFEMAnalogOutputPort(
            "con1",
            lf_fem,
            port_id = i + 4, 
        ), 
        sticky = StickyChannelAddon(duration = 16, digital = False), 
    )
    for i in [1, 2, 3]
]
sensor = [
    VoltageGate(
        id = "sensor_DC", 
        opx_output = LFFEMAnalogOutputPort(
            "con1",
            lf_fem,
            port_id = 8, 
        ), 
        sticky = StickyChannelAddon(duration = 16, digital = False), 
    )
]
resonator = ReadoutResonatorMW(
    id = "sensor_rf", 
    opx_output = MWFEMAnalogOutputPort(
        "con1", 
        mw_fem, 
        port_id = 1, 
        band = 1, 
        upconverter_frequency = 2e9,
    ), 
    opx_input = MWFEMAnalogInputPort(
        "con1", 
        mw_fem, 
        port_id = 1, 
        downconverter_frequency = 2e9,
        band = 1
    ), 
    intermediate_frequency=75e6,
    RF_frequency=2.075e9,
)

machine.create_virtual_gate_set(
    virtual_gate_names=[
        "virtual_dot_1", 
        "virtual_dot_2", 
        "virtual_dot_3", 
        "virtual_dot_4", 
        "virtual_barrier_1", 
        "virtual_barrier_2", 
        "virtual_barrier_3", 
        "virtual_sensor_1", 
    ],
    included_channels = plungers + barriers + sensor, 
    gate_set_id = "main_qpu"
    )

machine.register_channel_elements(
    plunger_channels = plungers, 
    barrier_channels = barriers, 
    sensor_channels_resonators = {
        sensor[0]: resonator
    }, 
)

machine.register_qubit(
    qubit_type = "loss_divincenzo",
    quantum_dots = [
        "virtual_dot_1", 
        "virtual_dot_2", 
        "virtual_dot_3"
    ]
)

machine.virtual_gate_sets["main_qpu"].add_point(
    name = "Idle", 
    voltages = {
        "virtual_dot_1" : 0.1, 
        "virtual_dot_2" : 0.05, 
        "virtual_dot_3" : 0.3, 
        "virtual_dot_4" : 0.1, 
        "virtual_barrier_1" : 0.3, 
        "virtual_barrier_2" : 0.35, 
        "virtual_barrier_3" : 0.32,
        "virtual_sensor_1" : 0.4
    }, 
    duration = 1000
)
machine.virtual_gate_sets["main_qpu"].add_point(
    name = "Operation", 
    voltages = {
        "virtual_dot_1" : 0.2, 
        "virtual_dot_2" : -0.02, 
        "virtual_dot_3" : 0.4, 
        "virtual_dot_4" : 0.3, 
        "virtual_barrier_1" : 0.4, 
        "virtual_barrier_2" : 0.6, 
        "virtual_barrier_3" : 0.22,
        "virtual_sensor_1" : 0.36
    }, 
    duration = 1000
)
machine.virtual_gate_sets["main_qpu"].add_point(
    name = "Readout", 
    voltages = {
        "virtual_dot_1" : 0.05, 
        "virtual_dot_2" : 0.1, 
        "virtual_dot_3" : 0.25, 
        "virtual_dot_4" : 0.15, 
        "virtual_barrier_1" : 0.3, 
        "virtual_barrier_2" : 0.35, 
        "virtual_barrier_3" : 0.37,
        "virtual_sensor_1" : 0.01
    }, 
    duration = 1000
)


from qm.qua import *

# with program() as prog: 
#     i = declare(int)
#     sequence = machine.voltage_sequences["main_qpu"]
#     with for_(i, 0, i<100, i+1):
#     #     sequence.step_to_point("Idle")
#     #     sequence.step_to_point("Operation")
#     #     sequence.step_to_point("Readout")
#     #     sequence.ramp_to_zero()

#         with sequence.simultaneous(duration = 1000): 
#             # Inside the simultaneous block, the voltages are all in one call. 
#             machine.qubits["virtual_dot_1"].step_to_voltages(0.4)
#             machine.qubits["virtual_dot_2"].step_to_voltages(0.2)
        
#         sequence.ramp_to_zero()


with program() as prog:
    i = declare(int)
    sequence = machine.voltage_sequences["main_qpu"]
    print(f"Sequence object: {sequence}")
    print(f"Batched voltages before: {sequence._batched_voltages}")
    
    with for_(i, 0, i<100, i+1):
        print("Entering simultaneous block")
        with sequence.simultaneous(duration = 1000): 
            print("Inside simultaneous, before dot1")
            print(f"Quantum dots: {list(machine.quantum_dots.keys())}")
            machine.quantum_dots["virtual_dot_1"].step_to_voltages(0.4)
            print(f"Batched after dot1: {sequence._batched_voltages}")
            machine.quantum_dots["virtual_dot_2"].step_to_voltages(0.2)
            print(f"Batched after dot2: {sequence._batched_voltages}")
        print("Exited simultaneous block")
        sequence.ramp_to_zero()

        
from qm import QuantumMachinesManager, SimulationConfig
qmm = QuantumMachinesManager(host = "172.16.33.115", cluster_name="CS_3")

config = machine.generate_config()

simulate = True


if simulate:
    # Simulates the QUA program for the specified duration
    simulation_config = SimulationConfig(duration=10_000//4)  # In clock cycles = 4ns
    # Simulate blocks python until the simulation is done
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
else:
    qm = qmm.open_qm(config)
    # Send the QUA program to the OPX, which compiles and executes it - Execute does not block python!
    job = qm.execute(prog)

