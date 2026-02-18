
import numpy as np

import matplotlib
import matplotlib.pyplot as plt
from quam.components.channels import SingleChannel

from quam_builder.architecture.quantum_dots.components.virtual_gate_set import (
    VirtualGateSet,
)

def _channels(names):
    return {
        name: SingleChannel(id=name, opx_output=("con", idx + 1))
        for idx, name in enumerate(names)
    }

matplotlib.use('TkAgg')
gate_set = VirtualGateSet(
    id="rectangular_roundtrip",
    channels=_channels(["P1", "P2", "P3"]),
)
gate_set.allow_rectangular_matrices = True

matrix = [
    [1.0, 0.2, -0.1],
    [0.0, 1.0, 0.5],
]
source_gates = ["V_bias", "V_sym"]
target_gates = ["P1", "P2", "P3"]
matrix_array = np.asarray(matrix)

gate_set.add_layer(
    source_gates=source_gates,
    target_gates=target_gates,
    matrix=matrix,
)

pinv_matrix = np.linalg.pinv(matrix_array)
source_samples = np.array(
    [
        [0.12, -0.05],
        [-0.08, 0.03],
        [0.05, 0.1],
        [-0.02, -0.08],
    ]
)
physical_samples = np.array([pinv_matrix @ source for source in source_samples])

resolved_samples = []
for source_vector in source_samples:
    resolved = gate_set.resolve_voltages(
        {gate: value for gate, value in zip(source_gates, source_vector)}
    )
    resolved_samples.append(
        np.array([resolved["P1"], resolved["P2"], resolved["P3"]])
    )
resolved_samples = np.array(resolved_samples)

np.testing.assert_allclose(resolved_samples, physical_samples, rtol=1e-9, atol=1e-9)

fig, axes = plt.subplots(1, 3, figsize=(9, 3), sharex=False, sharey=False)
for idx, channel in enumerate(target_gates):
    axes[idx].plot(
        physical_samples[:, idx],
        resolved_samples[:, idx],
        "o",
        label=f"{channel}",
    )
    axes[idx].plot(
        physical_samples[:, idx],
        physical_samples[:, idx],
        "--",
        color="gray",
        linewidth=0.8,
    )
    axes[idx].set_title(channel)
    axes[idx].set_xlabel("Original physical (V)")
    axes[idx].set_ylabel("Resolved physical (V)")
    axes[idx].legend()

fig.tight_layout()
plt.show()

# Example 2: More virtual sources than physical targets (tall matrix)
gate_set_tall = VirtualGateSet(
    id="rectangular_tall_example",
    channels=_channels(["P1", "P2"]),
)
gate_set_tall.allow_rectangular_matrices = True

matrix_tall = [
    [1.0, 0.2],
    [0.0, 1.0],
    [0.4, -0.6],
]
source_gates_tall = ["V_a", "V_b", "V_c"]
target_gates_tall = ["P1", "P2"]

gate_set_tall.add_layer(
    source_gates=source_gates_tall,
    target_gates=target_gates_tall,
    matrix=matrix_tall,
)

sample_virtual_voltages = {"V_a": 0.25, "V_b": -0.1, "V_c": 0.05}
resolved_physical = gate_set_tall.resolve_voltages(sample_virtual_voltages)
expected_physical = np.linalg.pinv(np.asarray(matrix_tall)) @ np.array(
    [sample_virtual_voltages[g] for g in source_gates_tall]
)

print(
    "Tall matrix example physical voltages:",
    {tg: resolved_physical[tg] for tg in target_gates_tall},
)
print("Expected (pinv) physical voltages:", expected_physical)

fig2, ax2 = plt.subplots(figsize=(5, 3))
indices = np.arange(len(target_gates_tall))
width = 0.35
resolved_array = np.array([resolved_physical[tg] for tg in target_gates_tall])

ax2.bar(indices - width / 2, resolved_array, width, label="resolved")
ax2.bar(indices + width / 2, expected_physical, width, label="expected (pinv)")
ax2.set_xticks(indices)
ax2.set_xticklabels(target_gates_tall)
ax2.set_ylabel("Voltage (V)")
ax2.set_title("Tall matrix resolution check")
ax2.legend()
fig2.tight_layout()
plt.show()