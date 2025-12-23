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
    pulses
) 
from quam.components.ports import (
    LFFEMAnalogOutputPort, 
    LFFEMAnalogInputPort,
    MWFEMAnalogOutputPort,
    MWFEMAnalogInputPort
)

from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.components import VoltageGate
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorSingle
from qm.qua import *


###########################################
###### Instantiate Physical Channels ######
###########################################
from qcodes import Instrument
from qcodes_contrib_drivers.drivers.QDevil.QDAC2 import QDac2
qdac_ip = "172.16.33.101"
lf_fem = 5
name = "QDAC"
try:
    qdac = Instrument.find_instrument(name)
except KeyError:
    qdac = QDac2(name, visalib='@py', address=f'TCPIP::{qdac_ip}::5025::SOCKET')

p1 = VoltageGate(id = f"plunger_1", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 1), qdac_channel = 1, sticky = StickyChannelAddon(duration = 16, digital = False))
p2 = VoltageGate(id = f"plunger_2", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 2), qdac_channel = 2, sticky = StickyChannelAddon(duration = 16, digital = False))
p3 = VoltageGate(id = f"plunger_3", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 3), qdac_channel = 3, sticky = StickyChannelAddon(duration = 16, digital = False))
p4 = VoltageGate(id = f"plunger_4", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 4), qdac_channel = 4, sticky = StickyChannelAddon(duration = 16, digital = False))
b1 = VoltageGate(id = f"barrier_1", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 5), qdac_channel = 5, sticky = StickyChannelAddon(duration = 16, digital = False))
b2 = VoltageGate(id = f"barrier_2", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 6), qdac_channel = 6, sticky = StickyChannelAddon(duration = 16, digital = False))
b3 = VoltageGate(id = f"barrier_3", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 7), qdac_channel = 7, sticky = StickyChannelAddon(duration = 16, digital = False))
s1 = VoltageGate(id = f"sensor_DC", opx_output = LFFEMAnalogOutputPort("con1", lf_fem, port_id = 8), qdac_channel = 8, sticky = StickyChannelAddon(duration = 16, digital = False))

p1.offset_parameter = qdac.channel(p1.qdac_channel).dc_constant_V
p2.offset_parameter = qdac.channel(p2.qdac_channel).dc_constant_V
p3.offset_parameter = qdac.channel(p3.qdac_channel).dc_constant_V
p4.offset_parameter = qdac.channel(p4.qdac_channel).dc_constant_V
b1.offset_parameter = qdac.channel(b1.qdac_channel).dc_constant_V
b2.offset_parameter = qdac.channel(b2.qdac_channel).dc_constant_V
b3.offset_parameter = qdac.channel(b3.qdac_channel).dc_constant_V
s1.offset_parameter = qdac.channel(s1.qdac_channel).dc_constant_V


from quam_builder.architecture.quantum_dots.components import VirtualDCSet

virtual_dc_set = VirtualDCSet(
    id = "Dots DC", 
    channels = {
        "plunger_1": p1, 
        "plunger_2": p2, 
        "plunger_3": p3, 
        "plunger_4": p4, 
        "barrier_1": b1, 
        "barrier_2": b2, 
        "barrier_3": b3, 
        "sensor_DC": s1
    }
)

virtual_dc_set.add_layer(
    layer_id = "cross_compensation", 
    source_gates = ["VP1", "VP2", "VP3", "VP4"], 
    target_gates = ["plunger_1", "plunger_2", "plunger_3", "plunger_4"], 
    matrix = [
        [1, 0.2, 0, 0.3], 
        [0.5, 1, 0.7, 0], 
        [0.3, 0, 1, 0.6], 
        [0, 0.1, 0.3, 1],
    ]
)

virtual_dc_set.add_layer(
    layer_id = "detuning_1", 
    source_gates = ["det_1", "det_2"], 
    target_gates = ["VP1", "VP2"], 
    matrix = [
        [0.8, 0.5], 
        [0.3, 0.7], 
    ]
)

virtual_dc_set.add_layer(
    layer_id = "detuning_2", 
    source_gates = ["det_3", "det_4"], 
    target_gates = ["VP3", "VP4"], 
    matrix = [
        [0.7, 0.4], 
        [0.6, 0.9], 
    ]
)
