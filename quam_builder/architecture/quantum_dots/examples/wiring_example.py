import matplotlib.pyplot as plt
from qualang_tools.wirer import Connectivity, Instruments, allocate_wiring, visualize

from qualang_tools.wirer.connectivity.wiring_spec import (
    WiringFrequency,
    WiringIOType,
    WiringLineType,
)
from qualang_tools.wirer.wirer.channel_specs import *
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.quantum_dots import build_base_quam, build_loss_divincenzo_quam, build_quam

# from quam_config import Quam
########################################################################################################################
# %%                                              Define static parameters
########################################################################################################################
host_ip = "127.0.0.1"  # QOP IP address
port = None  # QOP Port
cluster_name = "Cluster_1"  # Name of the cluster

########################################################################################################################
# %%                                      Define the available instrument setup
########################################################################################################################
instruments = Instruments()
instruments.add_mw_fem(controller=1, slots=[1])
instruments.add_lf_fem(controller=1, slots=[2, 3])

########################################################################################################################
# %%                                 Define which qubit ids are present in the system
########################################################################################################################
global_gates = [1, 2]
sensor_dots = [1, 2]
qubits = [1, 2, 3, 4, 5]
qubit_pairs = [(1, 2), (2, 3), (3, 4), (4, 5)]

########################################################################################################################
# %%                                 Define any custom/hardcoded channel addresses
########################################################################################################################
# multiplexed readout for sensor 1 to 2 and 3 to 4 on two feed-lines
s1to2_res_ch = mw_fem_spec(con=1, slot=1, in_port=1, out_port=1)
s3to4_res_ch = mw_fem_spec(con=1, slot=2, in_port=1, out_port=1)

########################################################################################################################
# %%                Allocate the wiring to the connectivity object based on the available instruments
########################################################################################################################
connectivity = Connectivity()
# The readout lines
# connectivity.add_voltage_gate_lines(voltage_gates=global_gates, name="rb")

# Option 1
# connectivity.add_sensor_dots(sensor_dots=sensor_dots, shared_resonator_line=True)

# Option 2
connectivity.add_sensor_dot_resonator_line(sensor_dots, shared_line=False, wiring_frequency=WiringFrequency.DC)
connectivity.add_sensor_dot_voltage_gate_lines(sensor_dots)

# Option 1:
# connectivity.add_qubits(qubits=qubits)
# Option 2:
connectivity.add_qubit_voltage_gate_lines(qubits)
connectivity.add_quantum_dot_qubit_drive_lines(qubits, wiring_frequency=WiringFrequency.RF, shared_line=True)

connectivity.add_qubit_pairs(qubit_pairs=qubit_pairs)
allocate_wiring(connectivity, instruments)

# Optional: visualize wiring (requires a GUI backend). Comment out in headless environments.
import matplotlib
matplotlib.use("TkAgg")
visualize(
    connectivity.elements,
    available_channels=instruments.available_channels,
    use_matplotlib=True,
)
plt.show()

########################################################################################################################
# %%                                   Build the wiring and QUAM
########################################################################################################################
machine = BaseQuamQD()

machine = build_quam_wiring(
    connectivity,
    host_ip,
    cluster_name,
    machine,
)

########################################################################################################################
# %%                              Build QUAM using Two-Stage Approach (Recommended)
########################################################################################################################

# STAGE 1: Build BaseQuamQD with physical quantum dots
# This creates the quantum dot layer without qubits, allowing you to:
# - Configure cross-compensation matrices
# - Calibrate quantum dot parameters
# - Save the state for later qubit configuration

machine = build_base_quam(
    machine,
    connect_qdac=True,  # Connect to external QDAC for voltage control
    qdac_ip="172.16.33.101",  # QDAC IP address
    save=True,  # Save the BaseQuamQD state
)

# At this point, you can:
# - Calibrate quantum dots
# - Update cross-compensation matrix
# - Add voltage points
# Then save and load later for Stage 2

# STAGE 2: Convert to LossDiVincenzoQuam and add qubits
# This is independent of Stage 1 and can be done later by loading the saved state
# Qubits are mapped implicitly: q1 → virtual_dot_1, q2 → virtual_dot_2, etc.

# Example: map qubit pairs to specific sensor dots (supports multiple sensors per pair)
# Pair keys: q1_q2 or q1-2. Sensor ids: virtual_sensor_<n>, sensor_<n>, or s<n>
qubit_pair_sensor_map = {
    "q1_q2": ["sensor_1"],
    "q2_q3": ["sensor_1", "sensor_2"],
    "q3_q4": ["sensor_2"],
}

machine = build_loss_divincenzo_quam(
    machine,  # Can also load from file: "path/to/base_quam_state"
    qubit_pair_sensor_map=qubit_pair_sensor_map,
    implicit_mapping=True,  # q1 → virtual_dot_1 mapping
    save=True,
)

# Now machine has both quantum dots AND qubits
# Access quantum dots: machine.quantum_dots["virtual_dot_1"]
# Access qubits: machine.qubits["q1"]
# Access qubit pairs: machine.qubit_pairs["q1_q2"]

########################################################################################################################
# %%                    Advanced: Manual XY Drive Wiring (Optional)
########################################################################################################################

# Normally, XY drives are extracted automatically from machine.wiring.
# But you can manually specify them if needed (e.g., when loading from file without wiring):

# xy_drive_wiring = {
#     "q1": {
#         "type": "IQ",  # IQ mixer drive
#         "wiring_path": "#/wiring/qubits/q1/xy",
#         "intermediate_frequency": 500e6,  # Optional, defaults to 500 MHz
#     },
#     "q2": {
#         "type": "MW",  # Microwave FEM drive
#         "wiring_path": "#/wiring/qubits/q2/xy",
#     },
# }
#
# machine = build_loss_divincenzo_quam(
#     "path/to/base_quam_state",
#     xy_drive_wiring=xy_drive_wiring,  # Manually specify XY drives
#     save=True,
# )

########################################################################################################################
# %%                         Alternative: Single-Call Convenience Wrapper
########################################################################################################################

# If you don't need the flexibility of two stages, use the convenience wrapper:
# machine = build_quam(
#     machine,
#     qubit_pair_sensor_map=qubit_pair_sensor_map,
#     connect_qdac=True,
#     qdac_ip="172.16.33.101",
#     save=True,
# )

########################################################################################################################
# %%                                      Generate QM Configuration
########################################################################################################################

# Generate the configuration for the Quantum Machines OPX
machine.generate_config()