import json
from pathlib import Path

from quam.components import SingleChannel
from quam_builder.architecture.neutral_atoms.base_quam_na import BaseQuamNA
from qm import qua
from qm.qua import wait

# -----------------------------
# Paths
# -----------------------------
script_dir = Path(__file__).parent  # This is tests/neutral_atoms/compile_demo
config_path = script_dir / "quam_config.json"
qua_path = script_dir / "compile_demo.qua"
state_path = script_dir / "state.json"

# -----------------------------
# 1. Create a dummy channel
# -----------------------------
my_channel = SingleChannel(opx_output=("con1", 1), id="ch1")

# Optional offset function simulating external voltage control
my_channel.offset_parameter = lambda v=None: print(f"Voltage set to {v} V") if v is not None else 0.0
my_channel.current_voltage = 0.0

# -----------------------------
# 2. Instantiate QPU
# -----------------------------
qpu = BaseQuamNA(channel=my_channel)

# -----------------------------
# 3. Set voltage
# -----------------------------
qpu.set_voltage(2.5)
print(f"Tracked voltage: {qpu.channel.current_voltage} V")

# -----------------------------
# 4. Generate config
# -----------------------------
config = qpu.generate_config()
print("Generated QUA config:", config)

# Save config JSON
with open(config_path, "w") as f:
    json.dump(config, f, indent=4)
print(f"Config saved to {config_path}")

# -----------------------------
# 5. Save trivial QUA program
# -----------------------------
with qua.program() as prog:
    wait(10, "ch1")  # wait 10 clock cycles on channel ch1
    pass  # trivial program

# Convert program to QUA text
qua_text = str(prog)

# Save QUA program as text
with open(qua_path, "w") as f:
    f.write(qua_text)
print(f"QUA program saved to {qua_path}")

print("Compile demo finished successfully!")

# Get a dict representation of the QPU
state = qpu.to_dict(follow_references=True, include_defaults=False) #qpu.save_state(state_path)

# Save as JSON
with open(state_path, "w") as f:
    json.dump(state, f, indent=4)
print(f"State saved to {state_path}")
