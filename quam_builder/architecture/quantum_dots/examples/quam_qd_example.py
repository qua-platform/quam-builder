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

5. Create your QUA programme
    - For simultaneous stepping/ramping, use either
        sequence = machine.voltage_sequences[gate_set_id]
        sequence.step_to_voltages({"virtual_dot_1": ..., "virtual_dot_2": ...})
    or use sequence.simultaneous:
        with sequence.simultaneous(duration = ...):
            machine.qubits["virtual_dot_1"].step_to_voltages(...)
            machine.qubits["virtual_dot_2"].step_to_voltages(...)

"""

from quam.components import (
    StickyChannelAddon,
    pulses,
    DigitalOutputChannel,
    Channel,
)
from quam.components.ports import (
    LFFEMAnalogOutputPort,
    LFFEMAnalogInputPort,
    MWFEMAnalogOutputPort,
    MWFEMAnalogInputPort,
)

from quam_builder.architecture.quantum_dots.components import (
    QuantumDot,
    VoltageGate,
    SensorDot,
    BarrierGate,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.components.voltage_gate import VoltageGate
from quam_builder.architecture.quantum_dots.components.dac_spec import QdacSpec
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.components.readout_resonator import (
    ReadoutResonatorSingle,
)
from quam_builder.architecture.quantum_dots.components.readout_transport import (
    ReadoutTransportSingle,
)
from quam_builder.architecture.quantum_dots.components.reservoir import DrainSingle
from qm.qua import *


# Instantiate Quam
machine = BaseQuamQD()
lf_fem = 6
mw_fem = 1

machine.network = {"host": "172.16.33.115", "cluster_name": "CS_4"}

###########################################
###### Instantiate Physical Channels ######
###########################################

p1 = VoltageGate(
    id=f"plunger_1",
    opx_output=LFFEMAnalogOutputPort(
        "con1", lf_fem, port_id=1, upsampling_mode="pulse"
    ),
    sticky=StickyChannelAddon(duration=16, digital=False),
)
p2 = VoltageGate(
    id=f"plunger_2",
    opx_output=LFFEMAnalogOutputPort(
        "con1", lf_fem, port_id=2, upsampling_mode="pulse"
    ),
    sticky=StickyChannelAddon(duration=16, digital=False),
)
p3 = VoltageGate(
    id=f"plunger_3",
    opx_output=LFFEMAnalogOutputPort(
        "con1", lf_fem, port_id=3, upsampling_mode="pulse"
    ),
    sticky=StickyChannelAddon(duration=16, digital=False),
)
p4 = VoltageGate(
    id=f"plunger_4",
    opx_output=LFFEMAnalogOutputPort(
        "con1", lf_fem, port_id=4, upsampling_mode="pulse"
    ),
    sticky=StickyChannelAddon(duration=16, digital=False),
)
b1 = VoltageGate(
    id=f"barrier_1",
    opx_output=LFFEMAnalogOutputPort(
        "con1", lf_fem, port_id=5, upsampling_mode="pulse"
    ),
    sticky=StickyChannelAddon(duration=16, digital=False),
)
b2 = VoltageGate(
    id=f"barrier_2",
    opx_output=LFFEMAnalogOutputPort(
        "con1", lf_fem, port_id=6, upsampling_mode="pulse"
    ),
    sticky=StickyChannelAddon(duration=16, digital=False),
)
b3 = VoltageGate(
    id=f"barrier_3",
    opx_output=LFFEMAnalogOutputPort(
        "con1", lf_fem, port_id=7, upsampling_mode="pulse"
    ),
    sticky=StickyChannelAddon(duration=16, digital=False),
)
s1 = VoltageGate(
    id=f"sensor_DC",
    opx_output=LFFEMAnalogOutputPort(
        "con1", lf_fem, port_id=8, upsampling_mode="pulse"
    ),
    sticky=StickyChannelAddon(duration=16, digital=False),
)


readout_pulse = pulses.SquareReadoutPulse(length=200, id="readout", amplitude=0.01)
resonator = ReadoutResonatorSingle(
    id="readout_resonator",
    frequency_bare=0,
    intermediate_frequency=500e6,
    operations={"readout": readout_pulse},
    opx_output=LFFEMAnalogOutputPort("con1", 5, port_id=1, upsampling_mode="mw"),
    opx_input=LFFEMAnalogInputPort("con1", 5, port_id=2),
)

drain = DrainSingle(
    id="drain",
    opx_output=("con1", lf_fem, 1),  # Dummy output
    readout=ReadoutTransportSingle(
        id="readout_transport",
        opx_input=LFFEMAnalogInputPort("con1", lf_fem, port_id=2),
    ),
)


#####################################
###### Create Virtual Gate Set ######
#####################################

# Create virtual gate set out of all the relevant HW channels.
# This function adds HW channels to machine.physical_channels, so no need to independently map
machine.create_virtual_gate_set(
    virtual_channel_mapping={
        "virtual_dot_1": p1,
        "virtual_dot_2": p2,
        "virtual_dot_3": p3,
        "virtual_dot_4": p4,
        "virtual_barrier_1": b1,
        "virtual_barrier_2": b2,
        "virtual_barrier_3": b3,
        "virtual_sensor_1": s1,
    },
    gate_set_id="main_qpu",
)


#########################################################
###### Register Quantum Dots, Sensors and Barriers ######
#########################################################

# Shortcut function to register QuantumDots, SensorDots, BarrierGates
machine.register_channel_elements(
    plunger_channels=[p1, p2, p3, p4],
    barrier_channels=[b1, b2, b3],
    sensor_resonator_mappings={s1: resonator},
    sensor_drain_mappings={s1: drain},
)

##################################################################
###### Connect the physical channels to the external source ######
##################################################################

qdac_connect = False
if qdac_connect:
    qdac_ip = "172.16.33.101"
    qdac_name = "main_QDAC"
    machine.set_dac_config(
        {
            qdac_name: {
                "driver_module": "qcodes_contrib_drivers.drivers.QDevil.QDAC2",
                "driver_class": "QDac2",
                "connection": {
                    "visalib": "@py",
                    "address": f"TCPIP::{qdac_ip}::5025::SOCKET",
                },
                "channel_method": "channel",
                "accessor": "dc_constant_V",
                "is_qdac": True,
            }
        }
    )
    # Set up the QDAC port specs
    for i, (ch_name, ch_obj) in enumerate(machine.physical_channels.items()):
        if isinstance(ch_obj, VoltageGate):
            ch_obj.dac_spec = QdacSpec(
                dac_name=qdac_name,
                opx_trigger_out=Channel(
                    id=f"{ch_name}_qdac_trigger",
                    digital_outputs={
                        "trigger": DigitalOutputChannel(
                            opx_output=("con1", lf_fem, i + 1), delay=0, buffer=0
                        )
                    },
                    operations={
                        "trigger": pulses.Pulse(length=100, digital_marker="ON")
                    },
                ),
                qdac_output_port=i + 1,
            )

    machine.connect_to_external_source()
    machine.create_virtual_dc_set("main_qpu")

########################################
###### Register Quantum Dot Pairs ######
########################################

# Register the quantum dot pairs
machine.register_quantum_dot_pair(
    id="dot1_dot2_pair",
    quantum_dot_ids=["virtual_dot_1", "virtual_dot_2"],
    sensor_dot_ids=["virtual_sensor_1"],
    barrier_gate_id="virtual_barrier_2",
)

machine.register_quantum_dot_pair(
    id="dot3_dot4_pair",
    quantum_dot_ids=["virtual_dot_3", "virtual_dot_4"],
    sensor_dot_ids=["virtual_sensor_1"],
    barrier_gate_id="virtual_barrier_3",
)

# Detuning axes ({id}_epsilon, matrix [[1, -1]]) are applied inside
# :meth:`BaseQuamQD.register_quantum_dot_pair`.

##################################################
###### Update the Cross Compensation Matrix ######
##################################################

# Update Cross Capacitance matrix values
machine.update_cross_compensation_submatrix(
    virtual_names=["virtual_barrier_1", "virtual_barrier_2"],
    channels=[p4],
    matrix=[[0.1, 0.5]],
    target="opx",
)

machine.update_cross_compensation_submatrix(
    virtual_names=["virtual_dot_1", "virtual_dot_2", "virtual_dot_3", "virtual_dot_4"],
    channels=[p1, p2, p3, p4],
    matrix=[
        [1, 0.1, 0.1, 0.3],
        [0.2, 1, 0.6, 0.8],
        [0.1, 0.3, 1, 0.3],
        [0.2, 0.5, 0.1, 1],
    ],
    target="opx",
)

###########################
###### Example Usage ######
###########################


# Let's define some example points.
# In this example, we would like to load virtual_dot_1 and virtual_dot_2 simultaneously. This will be performed in a sequence.simultaneous block.
# Remember that if these two dictionaries hold contradicting information about the voltage of a particular gate, the last one in the QUA programme wins.

# In this example, we purposefully keep all the barrier and sensor voltages identical, so that they can be initialised together, and no gate should hold two voltages at once.

qd_pairs = machine.quantum_dot_pairs

for pair_name, pair in qd_pairs.items():
    pair.add_point(
        point_name="initialize",
        voltages={
            "virtual_dot_1": 0.01,
            "virtual_dot_2": -0.02,
            "virtual_dot_3": 0.04,
            "virtual_dot_4": -0.02,
        },
    )
    pair.add_point(
        point_name="measure",
        voltages={
            "virtual_dot_1": 0.02,
            "virtual_dot_2": 0.01,
            "virtual_dot_3": -0.01,
            "virtual_dot_4": 0.04,
        },
    )
    pair.add_point(
        point_name="empty",
        voltages={
            "virtual_dot_1": -0.01,
            "virtual_dot_2": -0.01,
            "virtual_dot_3": 0.01,
            "virtual_dot_4": -0.04,
        },
    )

    for s in pair.sensor_dots:
        s._add_readout_params(pair_name, threshold=0.01)
