from qm import qua


# %% Load QUAM state and physical channels
from quam.core import QuamRoot

# Load QUAM state
machine = QuamRoot.load()

# Get physical channels
P1 = machine.channels["P1"]
P2 = machine.channels["P2"]
P3 = machine.channels["P3"]

# %% Define virtual set
from quam_builder.architecture.quantum_dots.other.virtual_gates import VirtualGateSet
# VirtualGateSet inherits from quam.components.quantum_components.quantum_component.QuantumComponent

# TODO Add check that channel.sticky is the same for all channels
virtual_gate_set = VirtualGateSet(
    # P1, P2, P3 are physical channels (elements)
    physical_gates={"P1": P1, "P2": P2, "P3": P3}
)

# %% Define virtual gate layer or layers

# - len(source_gates) must be equal to len(target_gates)
# - Multiple layers can be defined, but they cannot use the same source gates or target gates
# - For the first layer, target_gates are physical gates, but for subsequent layers they can be virtual gates
# - if target_gates is a subset of physical gates, the remaining physical gates are not affected by the virtual gate
#   Another way to think about it is that there is an additional virtual gate with the same name as the physical gate,
#   whose matrix elements are zero except for the physical gate
virtual_gate_set.add_layer(
  # Define virtual gate names
  source_gates=["vP1", "vP2"],
  # Define target (physical) gates, can also be a subset
  target_gates=["P1", "P2"],
  matrix=[[1, -0.1], [-0.2, 1]]
)

# %% Define tuning points
from quam_builder.architecture.quantum_dots.other.virtual_gates import VirtualTuningPoint
# VirtualTuningPoint inherits from quam.core.macro.quam_macro.QuamMacro

# Define tuning points
# Can contain combinations of physical and virtual gate voltages
# In this case, the virtual gate voltages will add a voltage on top of the specified physical gate voltages
virtual_gate_set.macros["readout"] = VirtualTuningPoint(duration=2000, vP1=0.05, vP2=0.1, P1=0.02)
# Optional alternative syntax:
# virtual_gate_set.add_point("readout", duration=2000, vP1=0.05, vP2=0.1, P1=0.02)

# %% Create QUA program
with qua.program() as prog:
    # The sequencer class should probably depend on whether sticky is True or False
    seq = virtual_gate_set.new_sequence()
    V_offset = qua.declare(qua.fixed)
    with qua.for_(V_offset, 0.3, V_offset < 0.32, V_offset + 0.01):
        # Plays square pulse at the coordinate using the default pulse length
        seq.go_to_point("readout")
        # Plays square pulse at coordinate using custom pulse length
        seq.go_to_point("readout", duration=500)
        # Ramp to coordinate and play pulse, total duration is length + ramp_duration
        seq.go_to_point("readout", ramp_duration=2000)
        seq.wait(1000)
        # Bring all voltages to zero        
        seq.ramp_to_zero(ramp_duration=100)

        seq.apply_compensation_pulse(max_amplitude=0.3)


# %% Generate QUA configuration
# Generate the default QUA configuration from QUAM state
config = machine.get_config()
# Add sequence-specific entries to the config
seq.apply_to_config(config)
