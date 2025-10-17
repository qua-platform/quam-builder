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

from quam_builder.architecture.quantum_dots.components import QuantumDot, VoltageGate, SensorDot, BarrierGate
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorMW

# Instantiate the quantum dots and the relevant barrier gates and sensor dots
dot1 = QuantumDot(id = "dot1", physical_channel = VoltageGate(opx_output = ("con1", 1)))
dot2 = QuantumDot(id = "dot2", physical_channel = VoltageGate(opx_output = ("con1", 2)))
dot3 = QuantumDot(id = "dot3", physical_channel = VoltageGate(opx_output = ("con1", 3)))
barrier_gate = BarrierGate(id = "barrier_gate", opx_output = ("con1", 1, 6))
sensor_dot = SensorDot(id = "sensor_gate_1", physical_channel = VoltageGate(opx_output = ("con1", 3)), readout_resonator = ReadoutResonatorMW(intermediate_frequency=2e6, opx_output = ("con1", 2, 1), opx_input = ("con1", 2, 2)))
sensor_dot_2 = SensorDot(id = "sensor_gate_2", physical_channel = VoltageGate(opx_output = ("con1", 3)), readout_resonator = ReadoutResonatorMW(intermediate_frequency=2e6, opx_output = ("con1", 2, 1), opx_input = ("con1", 2, 2)))


# For quantum dots in the system that are LD qubits, instantiate the qubit
qubit1 = LDQubit(quantum_dot = dot1)
qubit2 = LDQubit(quantum_dot = dot2)

# Instantiate the machine as a BaseQuamQD
machine = BaseQuamQD()

# Add the qubits to the machine
machine.qubits = {
    "Q1" : qubit1, 
    "Q2" : qubit2
}

# Add any miscellaneous quantum dots
machine.quantum_dots = {
    "dot3" : dot3
}

# Add all sensor dots and barrier gates of the machine
machine.sensor_dots = {
    "sensor1": sensor_dot, 
    "sensor2": sensor_dot_2
}
machine.barrier_gates["barrier1"] = barrier_gate


qubit_pair = LDQubitPair(
    qubit_control = machine.qubits["Q1"].get_reference(), 
    qubit_target = machine.qubits["Q2"].get_reference(), 
    barrier_gate = barrier_gate.get_reference(), 
    sensor_dots = [sensor_dot.get_reference()], 
    dot_coupling = 0.5
)

# Set the couplings values for the barrier gate and the sensor dot
qubit_pair.couplings[barrier_gate.id] = {
    qubit1.id: 0.01, 
    qubit2.id: 0.02
}
qubit_pair.couplings[sensor_dot.id] = {
    qubit1.id: 0.1, 
    qubit2.id: 0.2
}

# Attach the qubit pair to the machine
machine.qubit_pairs = {
    "qubit_pair_1" : qubit_pair
}

machine.create_virtual_gate_set(gate_set_id = "Virtual0")
print(machine.virtual_gate_sets["Virtual0"].valid_channel_names)

import numpy as np
print(np.array(machine.virtual_gate_sets["Virtual0"].layers[0].matrix))



machine.save("/Users/kalidu_laptop/Documents/example_QUAM")