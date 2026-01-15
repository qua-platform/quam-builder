import os
from pathlib import Path

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
from quam_builder.builder.quantum_dots import (
    build_base_quam,
    build_loss_divincenzo_quam,
    build_quam,
)

# from quam_config import Quam

EXAMPLES_DIR = Path(__file__).resolve().parent
os.environ.setdefault("QUAM_STATE_PATH", str(EXAMPLES_DIR / "quam_state"))
########################################################################################################################
# %%                                              Define static parameters
########################################################################################################################
host_ip = "172.16.33.115"  # QOP IP address
port = None  # QOP Port
cluster_name = "CS_3"  # Name of the cluster

########################################################################################################################
# %%                                      Define the available instrument setup
########################################################################################################################
instruments = Instruments()
instruments.add_mw_fem(controller=1, slots=[1])  # MW-FEM for RF drive lines (if using RF)
instruments.add_lf_fem(controller=1, slots=[2, 3])  # LF-FEM for DC gates and resonators
# Note: If you need more RF channels, add more MW-FEM slots:
# instruments.add_mw_fem(controller=1, slots=[1, 2])

########################################################################################################################
# %%                                 Define which quantum dot ids are present in the system
########################################################################################################################
global_gates = [1, 2]
sensor_dots = [1, 2]
quantum_dots = [1, 2, 3, 4, 5]
quantum_dot_pairs = [(1, 2), (2, 3), (3, 4), (4, 5)]

########################################################################################################################
# %%                                 Define any custom/hardcoded channel addresses
########################################################################################################################
# multiplexed readout for sensor 1 to 2 and 3 to 4 on two feed-lines
s1to2_res_ch = mw_fem_spec(con=1, slot=1, in_port=1, out_port=1)
s3to4_res_ch = mw_fem_spec(con=1, slot=2, in_port=1, out_port=1)

########################################################################################################################
# %%                    EXAMPLE 1: Two-Stage Workflow (Recommended for Calibration)
########################################################################################################################
# This workflow separates the dot-layer wiring (Stage 1) from qubit drive lines (Stage 2),
# allowing you to calibrate quantum dots before adding qubit drive lines.

print("=" * 80)
print("EXAMPLE 1: Two-Stage Workflow")
print("=" * 80)

# ============================================================================
# STAGE 1: Create connectivity WITHOUT drive lines (dot-layer only)
# ============================================================================
print("\n--- STAGE 1: Setting up connectivity WITHOUT drive lines ---")
connectivity_stage1 = Connectivity()

# Add global gates (readout bias lines)
connectivity_stage1.add_voltage_gate_lines(voltage_gates=global_gates, name="rb")

# Add sensor dots (voltage gates + resonator lines)
# Using convenience method that adds both voltage gates and resonator lines
connectivity_stage1.add_sensor_dots(sensor_dots=sensor_dots, shared_resonator_line=False, use_mw_fem=False)

# Add quantum dots with plunger gates ONLY (no drive lines)
# Note: add_drive_lines=False is the default, so we're only adding plunger gates
connectivity_stage1.add_quantum_dots(quantum_dots=quantum_dots, add_drive_lines=False)

# Add quantum dot pairs (barrier gates)
connectivity_stage1.add_quantum_dot_pairs(quantum_dot_pairs=quantum_dot_pairs)

# Allocate wiring
print("Allocating wiring for Stage 1...")
try:
    allocate_wiring(connectivity_stage1, instruments)
    print("✓ Stage 1 wiring allocation successful")
except Exception as e:
    print(f"✗ Error in allocate_wiring: {e}")
    import traceback
    traceback.print_exc()
    raise

# Build wiring and QUAM for Stage 1
print("\nBuilding QUAM for Stage 1 (dot-layer only)...")
try:
    machine_stage1 = BaseQuamQD()
    machine_stage1 = build_quam_wiring(
        connectivity_stage1,
        host_ip,
        cluster_name,
        machine_stage1,
    )
    print("✓ Stage 1 wiring and QUAM build successful")
except Exception as e:
    print(f"✗ Error in build_quam_wiring: {e}")
    import traceback
    traceback.print_exc()
    raise

# Build BaseQuamQD (quantum dots only, no qubits)
print("\nBuilding BaseQuamQD (quantum dots only)...")
try:
    machine_stage1 = build_base_quam(
        machine_stage1,
        connect_qdac=False,
        # qdac_ip="172.16.33.101",  # QDAC IP address
        save=True,  # Save the BaseQuamQD state
    )
    print("✓ Stage 1 BaseQuamQD build successful")
    print("  → You can now calibrate quantum dots, update cross-compensation matrix, etc.")
    print("  → Saved state can be loaded later for Stage 2")
except Exception as e:
    print(f"✗ Error in build_base_quam: {e}")
    import traceback
    traceback.print_exc()
    raise

# ============================================================================
# STAGE 2: Recreate connectivity WITH drive lines, then build full QUAM
# ============================================================================
print("\n" + "=" * 80)
print("--- STAGE 2: Setting up connectivity WITH drive lines ---")
print("=" * 80)

# Recreate instruments for Stage 2 (channels from Stage 1 may have been marked as used)
# Alternatively, you can reuse the same instruments object if block_used_channels=False
instruments_stage2 = Instruments()
instruments_stage2.add_mw_fem(controller=1, slots=[1])
instruments_stage2.add_lf_fem(controller=1, slots=[2, 3])

# Recreate connectivity with the same dot-layer wiring, but now add drive lines
connectivity_stage2 = Connectivity()

# Add the same dot-layer components as Stage 1
connectivity_stage2.add_voltage_gate_lines(voltage_gates=global_gates, name="rb")
connectivity_stage2.add_sensor_dots(sensor_dots=sensor_dots, shared_resonator_line=False, use_mw_fem=False)
connectivity_stage2.add_quantum_dot_pairs(quantum_dot_pairs=quantum_dot_pairs)

# Add quantum dots WITH drive lines this time
# Using convenience method that adds both plunger gates and drive lines
connectivity_stage2.add_quantum_dots(
    quantum_dots=quantum_dots,
    add_drive_lines=True,  # ← Key: Add drive lines in Stage 2
    use_mw_fem=True,  # Use MW-FEM for drive (set to False for LF-FEM)
    shared_drive_line=True,  # Share drive line across ALL quantum dots (saves channels - only needs 1 channel)
)

# Allocate wiring
print("Allocating wiring for Stage 2...")
try:
    allocate_wiring(connectivity_stage2, instruments_stage2)
    print("✓ Stage 2 wiring allocation successful")
except Exception as e:
    print(f"✗ Error in allocate_wiring: {e}")
    import traceback
    traceback.print_exc()
    raise

# Build wiring and QUAM for Stage 2
print("\nBuilding QUAM for Stage 2 (with drive lines)...")
try:
    machine_stage2 = build_quam_wiring(
        connectivity_stage2,
        host_ip,
        cluster_name,
        machine_stage1,
    )
    print("✓ Stage 2 wiring and QUAM build successful")
except Exception as e:
    print(f"✗ Error in build_quam_wiring: {e}")
    import traceback
    traceback.print_exc()
    raise

# Build full QUAM with qubits
print("\nBuilding LossDiVincenzoQuam (with qubits)...")
qubit_pair_sensor_map = {
    "q1_q2": ["sensor_1"],
    "q2_q3": ["sensor_1", "sensor_2"],
    "q3_q4": ["sensor_2"],
}

try:
    machine_stage2 = build_loss_divincenzo_quam(
        machine_stage2,
        qubit_pair_sensor_map=qubit_pair_sensor_map,
        implicit_mapping=True,  # q1 → virtual_dot_1 mapping
        save=True,
    )
    print("✓ Stage 2 LossDiVincenzoQuam build successful")
    print("  → Machine now has both quantum dots AND qubits with drive lines")
except Exception as e:
    print(f"✗ Error in build_loss_divincenzo_quam: {e}")
    import traceback
    traceback.print_exc()
    raise

########################################################################################################################
# %%                    EXAMPLE 2: Combined Workflow (Single-Stage)
########################################################################################################################
# This workflow creates connectivity with all components (including drive lines) in one go.
# Use this when you don't need to calibrate quantum dots separately.

print("\n" + "=" * 80)
print("EXAMPLE 2: Combined Workflow (Single-Stage)")
print("=" * 80)
print("\n--- Setting up connectivity WITH all components (including drive lines) ---")

# Create fresh instruments for the combined workflow
instruments_combined = Instruments()
instruments_combined.add_mw_fem(controller=1, slots=[1])
instruments_combined.add_lf_fem(controller=1, slots=[2, 3])

# Create connectivity with everything at once
connectivity_combined = Connectivity()

# Add global gates
connectivity_combined.add_voltage_gate_lines(voltage_gates=global_gates, name="rb")

# Add sensor dots
connectivity_combined.add_sensor_dots(sensor_dots=sensor_dots, shared_resonator_line=False, use_mw_fem=False)

# Add quantum dots WITH drive lines in a single call
connectivity_combined.add_quantum_dots(
    quantum_dots=quantum_dots,
    add_drive_lines=True,  # Include drive lines from the start
    use_mw_fem=True,  # Use MW-FEM for drive (set to False for LF-FEM)
    shared_drive_line=True,  # Share drive line across quantum dots (only needs 1 channel)
)

# Add quantum dot pairs
connectivity_combined.add_quantum_dot_pairs(quantum_dot_pairs=quantum_dot_pairs)

# Allocate wiring
print("Allocating wiring...")
try:
    allocate_wiring(connectivity_combined, instruments_combined)
    print("✓ Combined wiring allocation successful")
except Exception as e:
    print(f"✗ Error in allocate_wiring: {e}")
    import traceback
    traceback.print_exc()
    raise

# Build wiring and QUAM
print("\nBuilding QUAM (combined approach)...")
try:
    machine_combined = BaseQuamQD()
    machine_combined = build_quam_wiring(
        connectivity_combined,
        host_ip,
        cluster_name,
        machine_combined,
    )
    print("✓ Combined wiring and QUAM build successful")
except Exception as e:
    print(f"✗ Error in build_quam_wiring: {e}")
    import traceback
    traceback.print_exc()
    raise

# Build full QUAM using convenience wrapper
print("\nBuilding full QUAM using convenience wrapper...")
try:
    machine_combined = build_quam(
        machine_combined,
        qubit_pair_sensor_map=qubit_pair_sensor_map,
        connect_qdac=False,
        qdac_ip="172.16.33.101",
        save=True,
    )
    print("✓ Combined QUAM build successful")
except Exception as e:
    print(f"✗ Error in build_quam: {e}")
    import traceback
    traceback.print_exc()
    raise

########################################################################################################################
# %%                    Optional: Visualize Wiring
########################################################################################################################
# Uncomment to visualize wiring (requires a GUI backend)
# import matplotlib
# matplotlib.use("TkAgg")
# visualize(
#     connectivity_combined.elements,
#     available_channels=instruments_combined.available_channels,
#     use_matplotlib=True,
# )
# plt.show()

########################################################################################################################
# %%                                      Generate QM Configuration
########################################################################################################################
# Generate the configuration for the Quantum Machines OPX
# Uncomment to generate config:
# try:
#     machine_combined.generate_config()
#     print("✓ Configuration generation successful")
# except Exception as e:
#     print(f"✗ Error in generate_config: {e}")
#     import traceback
#     traceback.print_exc()
#     raise
