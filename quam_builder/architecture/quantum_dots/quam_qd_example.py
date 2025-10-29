"""

This is an example script on how to instantiate a QPU which contains Loss-DiVincenzo qubits, with other barrier gates and sensor dots. 

Workflow: 

1. Instantiate your machine. 

2. Instantiate the base hardware channels for the machine. 
    - In this example, arbitrary HW gates are created as VoltageGates. For QuantumDots and SensorDots, the base channel must be VoltageGate and sticky. They are instantiated in a mapping dictionary to be input into the machine

3. Create your VirtualGateSet. You do not need to manually add all the channels, the function create_virtual_gate_set should do it automatically. 
    Ensure that the mapping of the desired virtual gate to the relevant HW channel is correct, as the QuantumDot names will be extracted from this input dict. 

4. Register your components.  
    - Register the relevant QuantumDots, SensorDots and BarrierGates, mapped correctly to the relevant output channel. As long as the channel is correctly mapped, 
        the name of the element will be made consistent to that in the VirtualGateSet

5. Register Qubits and QubitPairs
    - Use machine.register_qubits to register qubits with their relevant type and associated dots. 

6. Create your QUA programme
    - For simultaneous stepping/ramping, use either 
        sequence = machine.voltage_sequences[gate_set_id]
        sequence.step_to_voltages({"qubit1": ..., "qubit2": ...})
    or use sequence.simultaneous: 
        with sequence.simultaneous(duration = ...): 
            machine.qubits["qubit1"].step_to_voltages(...)
            machine.qubits["qubit2"].step_to_voltages(...)

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

from quam_builder.architecture.quantum_dots.components import QuantumDot, VoltageGate, SensorDot, BarrierGate, XYDrive
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorMW, ReadoutResonatorSingle
from qm.qua import *


# Instantiate Quam
machine = BaseQuamQD()
lf_fem = 6
mw_fem = 1




###########################################
###### Instantiate Physical Channels ######
###########################################

p1 = VoltageGate(id = f"plunger_1", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 1), sticky = StickyChannelAddon(duration = 16, digital = False))
p2 = VoltageGate(id = f"plunger_2", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 2), sticky = StickyChannelAddon(duration = 16, digital = False))
p3 = VoltageGate(id = f"plunger_3", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 3), sticky = StickyChannelAddon(duration = 16, digital = False))
p4 = VoltageGate(id = f"plunger_4", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 4), sticky = StickyChannelAddon(duration = 16, digital = False))
b1 = VoltageGate(id = f"barrier_1", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 5), sticky = StickyChannelAddon(duration = 16, digital = False))
b2 = VoltageGate(id = f"barrier_2", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 6), sticky = StickyChannelAddon(duration = 16, digital = False))
b3 = VoltageGate(id = f"barrier_3", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 7), sticky = StickyChannelAddon(duration = 16, digital = False))
s1 = VoltageGate(id = f"sensor_DC", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 8), sticky = StickyChannelAddon(duration = 16, digital = False))

xy_q1 = XYDrive(id = "Q1_xy", opx_output = MWFEMAnalogOutputPort("con1",  mw_fem, port_id = 5, upconverter_frequency = 5e9, band = 2, full_scale_power_dbm=10))
xy_q2 = XYDrive(id = "Q2_xy", opx_output = MWFEMAnalogOutputPort("con1",  mw_fem, port_id = 6, upconverter_frequency = 5e9, band = 2, full_scale_power_dbm=10))
xy_q3 = XYDrive(id = "Q3_xy", opx_output = MWFEMAnalogOutputPort("con1",  mw_fem, port_id = 7, upconverter_frequency = 5e9, band = 2, full_scale_power_dbm=10))
xy_q4 = XYDrive(id = "Q4_xy", opx_output = MWFEMAnalogOutputPort("con1",  mw_fem, port_id = 8, upconverter_frequency = 5e9, band = 2, full_scale_power_dbm=10))


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


#####################################
###### Create Virtual Gate Set ######
#####################################

# Create virtual gate set out of all the relevant HW channels.
# This function adds HW channels to machine.physical_channels, so no need to independently map
machine.create_virtual_gate_set(
    virtual_channel_mapping = {
        "virtual_dot_1": p1,
        "virtual_dot_2": p2,
        "virtual_dot_3": p3,
        "virtual_dot_4": p4,
        "virtual_barrier_1": b1,
        "virtual_barrier_2": b2,
        "virtual_barrier_3": b3,
        "virtual_sensor_1": s1,
    },
    gate_set_id = "main_qpu"
)


#########################################################
###### Register Quantum Dots, Sensors and Barriers ######
#########################################################

# Shortcut function to register QuantumDots, SensorDots, BarrierGates
machine.register_channel_elements(
    plunger_channels = [p1, p2, p3, p4], 
    barrier_channels = [b1, b2, b3], 
    sensor_channels_resonators = [(s1, resonator)], 
)

#############################
###### Register Qubits ######
#############################


# Register qubits. For ST qubits, quantum_dots should be a tuple
machine.register_qubit(
    qubit_type = "loss_divincenzo",
    quantum_dot_id = "virtual_dot_1", 
    qubit_name = "Q1", 
    xy_channel = xy_q1
)

machine.register_qubit(
    qubit_type = "loss_divincenzo",
    quantum_dot_id = "virtual_dot_2", 
    qubit_name = "Q2", 
    xy_channel = xy_q2
)

machine.register_qubit(
    qubit_type = "loss_divincenzo",
    quantum_dot_id = "virtual_dot_3", 
    qubit_name = "Q3", 
    xy_channel = xy_q3
)

machine.register_qubit(
    qubit_type = "loss_divincenzo",
    quantum_dot_id = "virtual_dot_4", 
    qubit_name = "Q4", 
    xy_channel = xy_q4
)

########################################
###### Register Quantum Dot Pairs ######
########################################

# Register the quantum dot pairs
machine.register_quantum_dot_pair(
    id = "dot_pair_1",
    quantum_dot_ids = ["virtual_dot_1", "virtual_dot_2"], 
    sensor_dot_ids = ["virtual_sensor_1"], 
    barrier_gate_id = "virtual_barrier_2"
)

machine.register_quantum_dot_pair(
    id = "dot_pair_2",
    quantum_dot_ids = ["virtual_dot_3", "virtual_dot_4"], 
    sensor_dot_ids = ["virtual_sensor_1"],
    barrier_gate_id = "virtual_barrier_3"
)

# Define the detuning axes for both QuantumDotPairs
machine.quantum_dot_pairs["dot_pair_1"].define_detuning_axis(
    matrix = [[1,1],[1,-1]], 
    detuning_axis_name = "dot1_dot2_epsilon"
)

machine.quantum_dot_pairs["dot_pair_2"].define_detuning_axis(
    matrix = [[1,1],[1,-1]], 
    detuning_axis_name = "dot3_dot4_epsilon"
)

##################################
###### Register Qubit Pairs ######
##################################

# Register a Qubit Pair. Internally this checks for QuantumDotPair
machine.register_qubit_pair(
    id = "Q1_Q2", 
    qubit_type = "loss_divincenzo",
    qubit_control_name = "Q1", 
    qubit_target_name = "Q2", 
)

machine.register_qubit_pair(
    id = "Q3_Q4", 
    qubit_type = "loss_divincenzo",
    qubit_control_name = "Q3", 
    qubit_target_name = "Q4", 
)


###########################
###### Example Usage ######
###########################


# Define some example points

# Method 1: Add directly to VirtualGateSet
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

# Method 2: Add via function
machine.add_point(
    gate_set_id = "main_qpu",
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



# Update Cross Capacitance matrix values
machine.update_cross_compensation_submatrix(
    virtual_names = ["virtual_barrier_1", "virtual_barrier_2"], 
    channels = [p4], 
    matrix = [[0.1, 0.5]]
)

machine.update_cross_compensation_submatrix(
    virtual_names = ["virtual_dot_1", "virtual_dot_2", "virtual_dot_3", "virtual_dot_4"], 
    channels = [p1, p2, p3, p4], 
    matrix = [[1, 0.1, 0.1, 0.3], 
              [0.2, 1, 0.6, 0.8], 
              [0.1, 0.3, 1, 0.3], 
              [0.2, 0.5, 0.1, 1]]
)


# Example QUA programme: 
with program() as prog:
    i = declare(int)
    seq = machine.voltage_sequences["main_qpu"]
    with for_(i, 0, i<100, i+1):

        # Option 1 for simultaneous stepping
        seq.step_to_voltages({"virtual_dot_1": -0.4, "virtual_dot_2": -0.2}, duration = 1000)

        # Option 2 for simultaneous stepping: May be easier for the user
        with seq.simultaneous(duration = 1000): 
            machine.quantum_dots["virtual_dot_1"].go_to_voltages(0.4)
            machine.quantum_dots["virtual_dot_2"].go_to_voltages(0.2)
            machine.quantum_dot_pairs["dot_pair_2"].go_to_detuning(0.2)

        # Simulteneous ramping simply with a ramp_duration argument in seq.simultaneous
        with seq.simultaneous(duration = 1500, ramp_duration = 1500): 
            machine.quantum_dots["virtual_dot_3"].go_to_voltages(0.1)
            machine.quantum_dots["virtual_dot_4"].go_to_voltages(-0.2)

        # For sequential stepping, use outside of simultaneous block
        # These two commands will NOT happen simultaneously. Remember, commands can be used interchangeably with machine.qubits
        machine.qubits["Q3"].step_to_voltages(0.5, duration = 1000)
        machine.qubits["Q4"].step_to_voltages(0.1, duration = 1000)

        seq.ramp_to_zero()


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

