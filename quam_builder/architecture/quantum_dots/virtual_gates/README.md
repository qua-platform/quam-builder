# VirtualGateSet: Abstracting Gate Control with Virtualisation Layers

## 1. Introduction

This document introduces the **VirtualGateSet** and **VirtualisationLayer** components. These extend the physical gate control capabilities provided by `GateSet` and `VoltageSequence` by adding one or more layers of virtual gates.

Virtual gates simplify complex tuning procedures in experiments, especially for spin qubits, by allowing control over abstract parameters that map to multiple physical gate voltages.

`VirtualGateSet` builds upon `GateSet`, inheriting its ability to manage physical channels and tuning points, while adding the capability to define and apply virtualisation matrices.

## 2. Core Components

### 2.1 VirtualGateSet

A subclass of `GateSet`. It manages a list of `VirtualisationLayer` objects, which define the transformations from virtual gate voltages to underlying (either physical or lower-level virtual) gate voltages.

### 2.2 VirtualisationLayer

Represents a single linear transformation (matrix) from a set of source (virtual) gates to a set of target gates.

## 3. VirtualGateSet

A `VirtualGateSet` allows users to define and operate with virtual gates, abstracting the underlying physical gate operations.

**Key Features:**

- **Inherits from `GateSet`:** Retains all functionalities of `GateSet`, including physical channel management and `VoltageTuningPoint` definitions.
- **Manage Multiple Virtualisation Layers:** Stores a list of `VirtualisationLayer` objects. Multiple layers can be defined and stacked, allowing for hierarchical virtualisation. Layers are applied sequentially (in reverse order during voltage resolution) to translate top-level virtual gate voltages into physical gate voltages.
- **Add Layers:** Use `add_layer(source_gates, target_gates, matrix)` to define and append a new `VirtualisationLayer`:
  - `source_gates`: Names of the new virtual gates defined by this layer.
  - `target_gates`: Names of the gates (physical or virtual from a previous layer) that this layer maps onto.
  - `matrix`: The transformation matrix (list of lists of floats).
- **Additive Voltage Resolution:** Overrides `GateSet.resolve_voltages()`. When voltages are specified for virtual gates (potentially across different layers) and/or physical gates simultaneously, this method applies the inverse of the virtualisation matrices for each layer. Contributions from all specified virtual and physical gates are resolved and become additive at the physical gate level. Handles multi-layered virtualisation by processing layers from the outermost to the innermost.

### 3.1 Defining a `VirtualGateSet`

```python
from quam.components import SingleChannel
from quam_builder.architecture.quantum_dots.virtual_gates import VirtualGateSet

# Assume channel_P1, channel_P2 are existing SingleChannel objects
physical_channels = {"P1": channel_P1, "P2": channel_P2}
v_gate_set = VirtualGateSet(id="virt_dot_gates", channels=physical_channels)

# Add a first virtualisation layer (e.g., coarse tuning)
v_gate_set.add_layer(
    source_gates=["v_Coarse1", "v_Coarse2"],
    target_gates=["P1", "P2"],
    matrix=[[2.0, 1.0], [0.0, 1.0]]
)

# Add a second, higher-level virtualisation layer (e.g., fine tuning on top of coarse)
v_gate_set.add_layer(
    source_gates=["v_FineTune"],
    target_gates=["v_Coarse1"],
    matrix=[[0.5]]
)
```

## 4. VirtualisationLayer

A `VirtualisationLayer` defines a single step in the virtual-to-physical gate voltage transformation.

**Key Attributes:**

- `source_gates` (`List[str]`): Names of the virtual gates defined in this layer.
- `target_gates` (`List[str]`): Names of the physical or underlying virtual gates this layer maps to.
- `matrix` (`List[List[float]]`): The virtualisation matrix defining the linear transformation. The relationship is `V_source = M * V_target`. When resolving, `V_target = M_inverse * V_source` is used for this layer's contribution.
- Handles the calculation of the inverse matrix and the resolution of voltages for its specific layer.

## 5. Workflow and Usage

1. **Initialize `VirtualGateSet`:** Create an instance with the physical `SingleChannel` objects.
2. **Add Layers:** Use `v_gate_set.add_layer()` to define each virtualisation matrix. Multiple layers can be stacked.
3. **Create `VoltageSequence`:** Obtain a `VoltageSequence` from the `VirtualGateSet` instance:
   ```python
   vs = v_gate_set.new_sequence()
   ```
4. **Control Virtual (and Physical) Gates in QUA:** Use `VoltageSequence` methods (e.g., `step_to_level`, `go_to_point`) with virtual gate names, physical gate names, or a mix. The `VirtualGateSet` and `VoltageSequence` will automatically calculate the final physical voltages, summing contributions from all specified levels.

### 5.1 Example with `VoltageSequence` and Additive Control

```python
with qua.program() as my_virt_prog:
    voltage_seq.step_to_level(
        levels={
            "v_FineTune": 0.1,  # High-level virtual gate change
            "P2": 0.05          # Direct physical gate adjustment
        },
        duration=100  # ns
    )

# Resolution steps:
# 1. v_FineTune (0.1 V) -> v_Coarse1:
#    Inverse of [[0.5]] is [[2.0]], so contribution = 2.0 * 0.1 = 0.2 V.
# 2. v_Coarse1 and v_Coarse2 layer with inverse [[0.5, -0.5], [0.0, 1.0]]:
#    P1 += 0.5 * 0.2 = 0.1 V; P2 += 0.0 * 0.2 = 0.
# 3. Add direct P2 = 0.05 V.
# Final: P1 = 0.1 V; P2 = 0.05 V.
```

## 6. Relevance to Spin Qubits

Virtual gates are extremely powerful for operating spin qubits:

- **Orthogonal Control:** Provide more orthogonal control over quantum dot properties (e.g., independently tuning inter-dot tunnel coupling and dot chemical potential).
- **Hierarchical Tuning:** Multiple layers allow for a hierarchy of control, from coarse adjustments to fine-tuning.
- **Simplified Tuning:** Complex multi-dimensional tuning tasks become simpler in virtual gate space.
- **Automated Calibration:** Virtual gate matrices can be calibrated automatically, adapting to device changes.
- **Standardization:** Defines device operation in terms of abstract parameters rather than specific physical gate voltages, improving experiment portability and comparability.

The `VirtualGateSet` framework provides the necessary tools to implement these advanced control schemes within QUA.