from quam.components import StickyChannelAddon, pulses
from quam.components.ports import (
    LFFEMAnalogOutputPort,
    LFFEMAnalogInputPort,
)

from quam_builder.architecture.quantum_dots.components import VoltageGate, XYDrive
from quam_builder.architecture.quantum_dots.qpu import LossDiVincenzoQuam
from quam_builder.architecture.quantum_dots.components import ReadoutResonatorSingle
from quam.components.ports import (
    MWFEMAnalogOutputPort
)
from qm.qua import *

import numpy as np

# Instantiate Quam
machine = LossDiVincenzoQuam.load("/Users/kalidu_laptop/.qualibrate/quam_state")

#############################
###### Register Qubits ######
#############################
mw_fem = 1
mw_start_port = 1 
num_qubits = len(machine.quantum_dots)

# Register qubits. For ST qubits, quantum_dots should be a tuple
for i in range(num_qubits):
    machine.register_qubit(
        quantum_dot_id=f"virtual_dot_{i}",
        qubit_name=f"Q{i}",
        xy_channel = XYDrive(
            id = f"Q{i}_xy", opx_output = MWFEMAnalogOutputPort(
                "con1",  
                mw_fem, 
                port_id=mw_start_port + i,
                upconverter_frequency = 5e9, 
                band = 2, 
                full_scale_power_dbm=10), 
                intermediate_frequency = 5e6 + 1e6 * i, 
                operations = {"x90": pulses.GaussianPulse(length = 200, id= "x90_Gaussian", digital_marker = None, amplitude = 0.02, sigma = 50)}
        )
    )

########################################
###### Register Quantum Dot Pairs ######
########################################

# Register the quantum dot pairs
for i in range(len(machine.barrier_gates)):

    ##################################
    ###### Register Qubit Pairs ######
    ##################################
    qubit_id = f"Q{i}_Q{i+1}"
    # Register a Qubit Pair. Internally this checks for QuantumDotPair
    machine.register_qubit_pair(
        id=qubit_id,
        qubit_control_name=f"Q{i}",
        qubit_target_name=f"Q{i+1}",
    )

################################################
###### Set Preferred Readout Quantum Dots ######
################################################

for i in range(len(machine.quantum_dots)):
    neighbor_idx = i - 1 if i == len(machine.quantum_dots) - 1 else i + 1
    machine.qubits[f"Q{i}"].preferred_readout_quantum_dot = f"virtual_dot_{neighbor_idx}"

config = machine.generate_config()