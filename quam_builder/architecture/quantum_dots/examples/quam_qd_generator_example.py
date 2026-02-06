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
    - Use machine.register_qubit to register qubits with their associated dots.

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
    MWFEMAnalogOutputPort,
)

from quam_builder.architecture.quantum_dots.components import VoltageGate, XYDrive, QPU
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorSingle
from qm.qua import *

import numpy as np

# Instantiate Quam
machine = LossDiVincenzoQuam()
machine.qpu = QPU()
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
        operations={"readout": pulses.SquareReadoutPulse(length=200, id="readout", amplitude=0.01)},
        opx_output=LFFEMAnalogOutputPort("con1", lf_fem_resonators, port_id=i * 2 + next_port_id),
        opx_input=LFFEMAnalogInputPort("con1", lf_fem_resonators, port_id=i * 2 + 1 + next_port_id),
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
    allow_rectangular_matrices=True,
)


#########################################################
###### Register Quantum Dots, Sensors and Barriers ######
#########################################################

# Shortcut function to register QuantumDots, SensorDots, BarrierGates
machine.register_channel_elements(
    plunger_channels=ps,
    barrier_channels=bs,
    sensor_resonator_mappings={s: r for s, r in zip(ss, rs)},
)


########################################
###### Register Quantum Dot Pairs ######
########################################

# Register the quantum dot pairs
for i in range(barrier_gates):
    dot_id = f"dot{i}_dot{i+1}_pair"
    machine.register_quantum_dot_pair(
        id=dot_id,
        quantum_dot_ids=[f"virtual_dot_{j}" for j in [i, i + 1]],
        sensor_dot_ids=[f"virtual_sensor_{j}" for j in range(sensor_gates)],
        barrier_gate_id=f"virtual_barrier_{i}",
    )

    machine.quantum_dot_pairs[dot_id].define_detuning_axis(
        matrix=[[1, -1]], set_dc_virtual_axis=False
    )

#####################################
###### Register Qubits & Pairs  ######
#####################################

# Register one qubit per dot
mw_start_port = 1
for i in range(plunger_gates):
    xy_drive = XYDrive(
        id=f"Q{i}_xy",
        opx_output=MWFEMAnalogOutputPort(
            "con1",
            mw_fem,
            port_id=mw_start_port + i,
            upconverter_frequency=5e9,
            band=2,
            full_scale_power_dbm=10,
        ),
        intermediate_frequency=5e6 + 1e6 * i,
        operations={
            "x180": pulses.SquarePulse(
                length=120,
                id="x180",
                amplitude=0.25,
            ),
            "x90": pulses.SquarePulse(
                length=60,
                id="x90",
                amplitude=0.125,
            ),
            "y90": pulses.SquarePulse(
                length=60,
                id="y90",
                amplitude=0.125,
            ),
        },
    )
    machine.register_qubit(
        quantum_dot_id=f"virtual_dot_{i}",
        qubit_name=f"Q{i}",
        xy_channel=xy_drive,
    )

# Set a preferred readout quantum dot for each qubit
for i in range(plunger_gates):
    neighbor_idx = i - 1 if i == plunger_gates - 1 else i + 1
    machine.qubits[f"Q{i}"].preferred_readout_quantum_dot = f"virtual_dot_{neighbor_idx}"

# Register adjacent qubit pairs (Q0_Q1, Q1_Q2, ...)
for i in range(plunger_gates - 1):
    machine.register_qubit_pair(
        qubit_control_name=f"Q{i}",
        qubit_target_name=f"Q{i+1}",
        id=f"virtual_dot_{i}_virtual_dot_{i+1}",
    )

config = machine.generate_config()
