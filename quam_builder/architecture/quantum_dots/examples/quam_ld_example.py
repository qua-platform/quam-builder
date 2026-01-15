# pylint: skip-file

"""

This is an example script on how to instantiate a QPU which contains Loss-DiVincenzo qubits, with other barrier gates and sensor dots.

Workflow:

1. Instantiate your machine. You can load a BaseQuamQD to populate later, or load a populated LossDiVincenzoQuam.

2. Register your qubits and qubit pairs. They must be mapped onto existing quantum dots and QuantumDotPairs.

5. Create your QUA programme
    - For simultaneous stepping/ramping, use either
        sequence = machine.voltage_sequences[gate_set_id]
        sequence.step_to_voltages({"Q1": ..., "Q2": ...})
    or use sequence.simultaneous:
        with sequence.simultaneous(duration = ...):
            machine.qubits["Q1"].step_to_voltages(...)
            machine.qubits["Q2"].step_to_voltages(...)

"""

from quam.components.ports import MWFEMAnalogOutputPort
from quam.components import pulses

from quam_builder.architecture.quantum_dots.components import XYDrive
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from qm.qua import *

machine = LossDiVincenzoQuam.load("/Users/kalidu_laptop/.qualibrate/quam_state")

lf_fem = 6
mw_fem = 1

xy_q1 = XYDrive(
    id="Q1_xy",
    opx_output=MWFEMAnalogOutputPort(
        "con1", mw_fem, port_id=5, upconverter_frequency=5e9, band=2, full_scale_power_dbm=10
    ),
    intermediate_frequency=10e6,
    operations={"x90": pulses.GaussianPulse(length=200, amplitude=0.01, sigma=50)},
)
xy_q2 = XYDrive(
    id="Q2_xy",
    opx_output=MWFEMAnalogOutputPort(
        "con1", mw_fem, port_id=6, upconverter_frequency=5e9, band=2, full_scale_power_dbm=10
    ),
    intermediate_frequency=12e6,
    operations={"x90": pulses.GaussianPulse(length=200, amplitude=0.01, sigma=50)},
)
xy_q3 = XYDrive(
    id="Q3_xy",
    opx_output=MWFEMAnalogOutputPort(
        "con1", mw_fem, port_id=7, upconverter_frequency=5e9, band=2, full_scale_power_dbm=10
    ),
    intermediate_frequency=13e6,
    operations={"x90": pulses.GaussianPulse(length=200, amplitude=0.01, sigma=50)},
)
xy_q4 = XYDrive(
    id="Q4_xy",
    opx_output=MWFEMAnalogOutputPort(
        "con1", mw_fem, port_id=8, upconverter_frequency=5e9, band=2, full_scale_power_dbm=10
    ),
    intermediate_frequency=14e6,
    operations={"x90": pulses.GaussianPulse(length=200, amplitude=0.01, sigma=50)},
)


#############################
###### Register Qubits ######
#############################


# Register qubits. For ST qubits, quantum_dots should be a tuple
machine.register_qubit(
    qubit_name="Q1",
    quantum_dot_id="virtual_dot_1",
    readout_quantum_dot="virtual_dot_2",
    xy_channel=xy_q1,
)

machine.register_qubit(
    qubit_name="Q2",
    quantum_dot_id="virtual_dot_2",
    readout_quantum_dot="virtual_dot_1",
    xy_channel=xy_q2,
)

machine.register_qubit(
    qubit_name="Q3",
    quantum_dot_id="virtual_dot_3",
    readout_quantum_dot="virtual_dot_4",
    xy_channel=xy_q3,
)

machine.register_qubit(
    qubit_name="Q4",
    quantum_dot_id="virtual_dot_4",
    readout_quantum_dot="virtual_dot_3",
    xy_channel=xy_q4,
)

# Fill out the grid location and arbitrary larmor frequencies of the qubit
for i in range(1, 5):
    machine.quantum_dots[f"Q{i}"].grid_location = f"0,{i}"
    machine.quantum_dots[f"Q{i}"].larmor_frequency = 5e6 + 1e6 * i

##################################
###### Register Qubit Pairs ######
##################################

# Register a Qubit Pair. Internally this checks for QuantumDotPair
machine.register_qubit_pair(
    id="Q1_Q2",
    qubit_control_name="Q1",
    qubit_target_name="Q2",
)

machine.register_qubit_pair(
    id="Q3_Q4",
    qubit_control_name="Q3",
    qubit_target_name="Q4",
)


###########################
###### Example Usage ######
###########################


# Let's define some example points.
# In this example, we would like to initialise Q1 and Q2 simultaneously. This will be performed in a sequence.simultaneous block.
# Remember that if these two dictionaries hold contradicting information about the voltage of a particular gate, the last one in the QUA programme wins.

# In this example, we purposefully keep all the barrier and sensor voltages identical, so that they can be initialised together, and no gate should hold two voltages at once.
# Notice that we have not identified any points for Q3 or Q4. The associated QDs will be kept constant.


machine.quantum_dots["Q1"].add_point(
    point_name="initialisation",
    voltages={
        "virtual_dot_1": 0.1,
    },
    replace_existing_point=True,
)

machine.quantum_dots["Q2"].add_point(
    point_name="initialisation",
    voltages={
        "virtual_dot_2": 0.15,
    },
    replace_existing_point=True,
)

# We can also initialise a tuning point for a qubit pair:
machine.quantum_dot_pairs["Q3_Q4"].add_point(
    point_name="some_two_qubit_gate",
    voltages={
        "virtual_dot_3": 0.2,
        "virtual_dot_4": 0.25,
    },
    replace_existing_point=True,
)


# # Example QUA programme:
# with program() as prog:
#     i = declare(int)
#     seq = machine.voltage_sequences["main_qpu"]
#     with for_(i, 0, i<100, i+1):

#         # Option 1 for simultaneous stepping
#         seq.step_to_voltages({"virtual_dot_1": -0.4, "virtual_dot_2": -0.2}, duration = 1000)

#         # Option 2 for simultaneous stepping: May be easier for the user
#         with seq.simultaneous(duration = 1000):
#             machine.qubits["Q1"].go_to_voltages(0.4)
#             machine.qubits["Q2"].go_to_voltages(0.2)
#             machine.qubit_pairs["Q3_Q4"].step_to_voltages(0.2)

#         # Simulteneous ramping simply with a ramp_duration argument in seq.simultaneous
#         with seq.simultaneous(duration = 1500, ramp_duration = 1500):
#             machine.qubits["Q1"].go_to_voltages(0.1)
#             machine.qubits["Q2"].go_to_voltages(-0.2)

#         # For sequential stepping, use outside of simultaneous block
#         # These two commands will NOT happen simultaneously. Remember, commands can be used interchangeably with machine.qubits
#         machine.qubits["Q3"].step_to_voltages(0.5, duration = 1000)
#         machine.qubits["Q4"].step_to_voltages(0.1, duration = 1000)

#         # Can also use point macros saved in qubit and QD objects, inside a simultaneous block.
#         # Remember that no point should have repeated dict entries, as this would indicate a gate should be at two voltages at once!
#         with seq.simultaneous(duration = 1000):
#             machine.qubits["Q1"].step_to_point("initialisation")
#             machine.qubits["Q2"].step_to_point("initialisation")
#             machine.qubit_pairs["Q3_Q4"].step_to_point("some_two_qubit_gate")
#             # If there are repeated dict entries, internally, the last entered voltage for that particular gate wins.

#         machine.qubits["Q1"].sensor_dots[0].readout_resonator.measure("readout")
#         seq.ramp_to_zero()


# from qm import QuantumMachinesManager, SimulationConfig
# qmm = QuantumMachinesManager(host = "172.16.33.115", cluster_name="CS_3")

# config = machine.generate_config()

# simulate = True


# if simulate:
#     # Simulates the QUA program for the specified duration
#     simulation_config = SimulationConfig(duration=10_000//4)  # In clock cycles = 4ns
#     # Simulate blocks python until the simulation is done
#     job = qmm.simulate(config, prog, simulation_config)
#     # Get the simulated samples
#     samples = job.get_simulated_samples()
#     # Plot the simulated samples
#     samples.con1.plot()
#     # Get the waveform report object
#     waveform_report = job.get_simulated_waveform_report()
#     # Cast the waveform report to a python dictionary
#     waveform_dict = waveform_report.to_dict()
#     # Visualize and save the waveform report
#     waveform_report.create_plot(samples, plot=True)
# else:
#     qm = qmm.open_qm(config)
#     # Send the QUA program to the OPX, which compiles and executes it - Execute does not block python!
#     job = qm.execute(prog)
