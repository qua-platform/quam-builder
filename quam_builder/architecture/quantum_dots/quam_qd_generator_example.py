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

from quam.components import StickyChannelAddon, pulses
from quam.components.ports import (
    LFFEMAnalogOutputPort,
    LFFEMAnalogInputPort,
)

from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorSingle
from qm.qua import *


# Instantiate Quam
machine = BaseQuamQD()
lf_fem_dots = 6
lf_fem_resonators = 5
mw_fem = 1
plunger_gates = 6
barrier_gates = plunger_gates - 1
sensor_gates = 2
resonators = 2

###########################################
###### Instantiate Physical Channels ######
###########################################
next_port_id = 0

ps = [
    VoltageGate(
        id=f"plunger_{i}",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem_dots, port_id=i + next_port_id),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    for i in range(plunger_gates)
]

next_port_id += plunger_gates

bs = [
    VoltageGate(
        id=f"barrier_{i}",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem_dots, port_id=i + next_port_id),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    for i in range(barrier_gates)
]

next_port_id += barrier_gates

ss = [
    VoltageGate(
        id=f"sensor_{i}",
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem_dots, port_id=i + next_port_id),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    for i in range(sensor_gates)
]

next_port_id += sensor_gates

next_port_id = 0

rs = [
    ReadoutResonatorSingle(
        id=f"readout_resonator_{i}",
        frequency_bare=0,
        intermediate_frequency=500e6,
        operations={
            "readout": pulses.SquareReadoutPulse(
                length=200, id="readout", amplitude=0.01
            )
        },
        opx_output=LFFEMAnalogOutputPort(
            "con1", lf_fem_resonators, port_id=i * 2 + next_port_id
        ),
        opx_input=LFFEMAnalogInputPort(
            "con1", lf_fem_resonators, port_id=i * 2 + 1 + next_port_id
        ),
        sticky=StickyChannelAddon(duration=16, digital=False),
    )
    for i in range(resonators)
]
next_port_id += resonators * 2


#####################################
###### Create Virtual Gate Set ######
#####################################

# Create virtual gate set out of all the relevant HW channels.
# This function adds HW channels to machine.physical_channels, so no need to independently map
machine.create_virtual_gate_set(
    virtual_channel_mapping={
        **{f"virtual_dot_{i}": p for i, p in enumerate(ps)},
        **{f"virtual_barrier_{i}": b for i, b in enumerate(bs)},
        **{f"virtual_sensor_{i}": s for i, s in enumerate(ss)},
    },
    gate_set_id="main_qpu",
)


#########################################################
###### Register Quantum Dots, Sensors and Barriers ######
#########################################################

# Shortcut function to register QuantumDots, SensorDots, BarrierGates
machine.register_channel_elements(
    plunger_channels=ps,
    barrier_channels=bs,
    sensor_channels_resonators=[(s, r) for s, r in zip(ss, rs)],
)

#############################
###### Register Qubits ######
#############################


# Register qubits. For ST qubits, quantum_dots should be a tuple
for i in range(plunger_gates):
    machine.register_qubit(
        qubit_type="loss_divincenzo",
        quantum_dot_id=f"virtual_dot_{i}",
        id=f"Q{i}",
    )

########################################
###### Register Quantum Dot Pairs ######
########################################

# Register the quantum dot pairs
for i in [0]:
    dot_id = f"dot{i}_dot{i+1}_pair"
    machine.register_quantum_dot_pair(
        id=dot_id,
        quantum_dot_ids=[f"virtual_dot_{j}" for j in [i, i + 1]],
        sensor_dot_ids=[f"virtual_sensor_{j}" for j in range(sensor_gates)],
        barrier_gate_id=f"virtual_barrier_{i}",
    )

    machine.quantum_dot_pairs[dot_id].define_detuning_axis(matrix=[[1, 1], [1, -1]])

    ##################################
    ###### Register Qubit Pairs ######
    ##################################
    qubit_id = f"Q{i}_Q{i+1}"
    # Register a Qubit Pair. Internally this checks for QuantumDotPair
    machine.register_qubit_pair(
        id=qubit_id,
        qubit_type="loss_divincenzo",
        qubit_control_id=f"Q{i}",
        qubit_target_id=f"Q{i+1}",
    )

config = machine.generate_config()


from qm import QuantumMachinesManager, SimulationConfig
qmm = QuantumMachinesManager(host = "192.168.88.11", cluster_name="CS_1")

qm = qmm.open_qm(config)
# Send the QUA program to the OPX, which compiles and executes it - Execute does not block python!
# job = qm.execute(prog)
