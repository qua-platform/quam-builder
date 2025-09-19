# VirtualGateSet: Abstracting Gate Control with Virtualisation Layers

## 1. Introduction

This document introduces the **VirtualGateSet** and **VirtualisationLayer** components. These extend the physical gate control capabilities provided by `GateSet` and `VoltageSequence` by adding one or more layers of virtual gates.

Virtual gates simplify complex tuning procedures in experiments, especially for spin qubits, by allowing control over abstract parameters that map to multiple physical gate voltages.

**`VirtualGateSet` builds upon `GateSet` and inherits all of its features**, including physical channel management, `VoltageTuningPoint` definitions, and all voltage control methods. This means you can use virtual gates while still having access to all the voltage control capabilities of the underlying `GateSet`.

## 2. Core Components

### 2.1 VirtualGateSet

A subclass of `GateSet`. It manages a list of `VirtualisationLayer` objects, which define the transformations from virtual gate voltages to underlying (either physical or lower-level virtual) gate voltages.

### 2.2 VirtualisationLayer

Represents a single linear transformation (matrix) from a set of source (virtual) gates to a set of target gates.

### 2.3 Complete Example

This section provides a complete example of the workflow before getting into the specifics, so that you have an idea of what the finished program might look like. 

#### 2.3.1 Instantiate your VirtualGateSet

    This first section assumes you have already instantiated VoltageGate or SingleChannel objects. For a concrete example, check section 8. The VirtualGateSet instantiation is identical to that of GateSet


    ```python
    from quam.components import SingleChannel
    from quam_builder.architecture.quantum_dots.virtual_gates import VirtualGateSet

    # Physical channels for a double quantum dot
    physical_channels = {"P1": channel_P1, "P2": channel_P2, "P3": channel_P3}
    v_gate_set = VirtualGateSet(id="double_dot_gates", channels=physical_channels)

    ```

#### 2.3.2 Add Virtualisation Layers 

    You can map virtualisation layers onto your existing physical or virtual gates using the `.add_layer()` method. You must name the new virtual `source_gates` and input a transformation matrix. This does not need to map onto all of your existing physical or virtual gates. 

    ```python
    # Add coarse tuning layer (virtual gates for overall dot positions)
    v_gate_set.add_layer(
        source_gates=["v_Coarse1", "v_Coarse2"],
        target_gates=["P1", "P2"],
        matrix=[[1.0, 0.5], [0.5, 1.0]]  # Coupled control
    )

    # Add fine tuning layer (virtual gates for precise adjustments)
    v_gate_set.add_layer(
        source_gates=["v_FineTune1", "v_FineTune2"],
        target_gates=["v_Coarse1", "v_Coarse2"],
        matrix=[[0.1, 0.0], [0.0, 0.1]]  # Small adjustments
    )
    ```

#### 2.3.3 Add `VoltageTuningPoints` if needed 

    The `VoltageTuningPoint` can comprise of any combination of physical and virtual gates. 

    ```python
    # Add a predefined tuning point for readout
    v_gate_set.add_point(name="readout", voltages={"v_Coarse1": 0.2, "v_Coarse2": 0.1}, duration=1000)
    ```

#### 2.3.4 Create your QUA program with your `VoltageSequence`

    Instantiate your new sequence in the QUA programme, and step/ramp to any point.


    ```python
    # Create voltage sequence
    with qua.program() as complex_control:
        voltage_seq = v_gate_set.new_sequence()

        # Step to a virtual gate configuration
        voltage_seq.step_to_voltages(
            voltages={"v_FineTune1": 0.05, "v_FineTune2": -0.02},
            duration=500
        )

        # Ramp to a predefined point
        voltage_seq.ramp_to_point("readout", ramp_duration=100, duration=2000)

        # Combine virtual and physical control
        voltage_seq.step_to_voltages(
            voltages={
                "v_FineTune1": 0.1,    # Virtual gate adjustment
                "P3": 0.3              # Direct physical gate control
            },
            duration=1000
        )

        # Fine ramp with virtual gates
        voltage_seq.ramp_to_voltages(
            voltages={"v_FineTune2": 0.0},
            duration=500,
            ramp_duration=40 # Ensure multiple of 4
        )

        # Return to zero
        voltage_seq.ramp_to_zero(ramp_duration=200)

    # The system automatically resolves all virtual gate contributions:
    # - v_FineTune1 (0.1V) -> v_Coarse1: 0.1V contribution
    # - v_FineTune2 (0.0V) -> v_Coarse2: 0.0V contribution
    # - v_Coarse1 (0.1V) + readout (0.2V) -> P1: 0.3V total
    # - v_Coarse2 (0.0V) + readout (0.1V) -> P2: 0.1V total
    # - P3: 0.3V direct control
    ```

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

### 3.1 Important Behavior: Unspecified Virtual Gates Are Zeroed Per Operation

Each `VoltageSequence` call (e.g., `step_to_voltages`, `ramp_to_voltages`, `step_to_point`) is resolved independently. Any virtual gate not explicitly provided in a call is assumed to be 0 V for that operation. This effectively removes any prior contribution from that virtual gate in the resolved physical voltages.

- This applies at every layer. If a higher-level virtual gate is not specified, its contribution is taken as 0 V when resolving to lower levels.
- Physical channels not specified in a call are also driven to 0 V for that operation (same behavior as `GateSet`).

Implication: Virtual gates do not “remember” their last values across operations. If you want to maintain a virtual configuration, include all relevant virtual gates and their values in each call, or operate directly on physical gates.

Example:

```python
# Suppose v_C1 and v_C2 map to P1, P2 via a layer

# First call: set both virtual gates
voltage_seq.step_to_voltages({"v_C1": 0.2, "v_C2": 0.1}, duration=1000)

# Second call: only specify v_C1
# v_C2 is assumed 0 V for this call, so its previous contribution is removed
voltage_seq.step_to_voltages({"v_C1": 0.2}, duration=1000)
```


## 4. VirtualisationLayer

A `VirtualisationLayer` defines a single step in the virtual-to-physical gate voltage transformation.

**Key Attributes:**

- `source_gates` (`List[str]`): Names of the virtual gates defined in this layer.
- `target_gates` (`List[str]`): Names of the physical or underlying virtual gates this layer maps to.
- `matrix` (`List[List[float]]`): The virtualisation matrix defining the linear transformation. The relationship is `V_source = M * V_target`. When resolving, `V_target = M_inverse * V_source` is used for this layer's contribution.
- Handles the calculation of the inverse matrix and the resolution of voltages for its specific layer.

### Mathematical Relations

#### 4.1 Forward Transformation (Virtual to Physical)

The core mathematical relationship for each virtualisation layer is:

```
V_target = M * V_source
```

Where:

- `V_source` is the vector of virtual gate voltages (source gates)
- `V_target` is the vector of target gate voltages (physical or lower-level virtual gates)
- `M` is the transformation matrix

For example, with a 2x2 matrix:

```python
matrix = [[1.0, 0.5], [0.5, 1.0]]
source_gates = ["v_Gate1", "v_Gate2"]
target_gates = ["P1", "P2"]
```

The relationship becomes:

```
[P1]   [1.0  0.5] [v_Gate1]
[P2] = [0.5  1.0] [v_Gate2]
```

Expanded:

- `P1 = 1.0 * v_Gate1 + 0.5 * v_Gate2`
- `P2 = 0.5 * v_Gate1 + 1.0 * v_Gate2`

#### 4.2 Inverse Transformation (Voltage Resolution)

During voltage resolution, the system applies the inverse transformation:

```
V_source = M⁻¹ * V_target
```

The code implements this using `numpy.linalg.inv()` to calculate the inverse matrix. For each layer's resolution:

```python
inverse_matrix = np.linalg.inv(matrix)
for target_gate, inv_matrix_row in zip(target_gates, inverse_matrix):
    resolved_voltages[target_gate] += inv_matrix_row @ source_voltages
```

#### 4.3 Multi-Layer Resolution

For multiple virtualisation layers, transformations are applied sequentially in reverse order. Consider two layers:

**Layer 1:** `v_Coarse1, v_Coarse2 → P1, P2`

```
matrix_1 = [[1.0, 0.5], [0.5, 1.0]]
```

**Layer 2:** `v_Fine1, v_Fine2 → v_Coarse1, v_Coarse2`

```
matrix_2 = [[0.1, 0.0], [0.0, 0.1]]
```

The combined transformation is:

```
[P1]   [1.0  0.5] [0.1  0.0] [v_Fine1]
[P2] = [0.5  1.0] [0.0  0.1] [v_Fine2]
```

Which gives the overall relationship:

```
[P1]   [0.1  0.05] [v_Fine1]
[P2] = [0.05 0.1 ] [v_Fine2]
```

#### 4.4 Additive Voltage Contributions

The system supports additive contributions from different layers and direct physical gate control. If you specify:

- `v_Fine1 = 1.0V` (from Layer 2)
- `v_Coarse1 = 0.2V` (from Layer 1)
- `P1 = 0.1V` (direct)

The final voltage for P1 becomes:

```
P1_final = P1_direct + P1_from_v_Coarse1 + P1_from_v_Fine1
         = 0.1 + (1.0 * 0.2) + (1.0 * 0.1)
         = 0.1 + 0.2 + 0.1 = 0.4V
```

##### 4.5 Matrix Constraints

For a valid virtualisation layer:

- Matrix must be square: `len(source_gates) == len(target_gates)`
- Matrix must be invertible (non-singular): `det(M) ≠ 0`
- The inverse matrix is calculated using `numpy.linalg.inv(matrix)`


## 5. Workflow and Usage

1. **Initialize `VirtualGateSet`:** Create an instance with the physical `SingleChannel` objects.
2. **Add Layers:** Use `v_gate_set.add_layer()` to define each virtualisation matrix. Multiple layers can be stacked.
3. **Create `VoltageSequence`:** Obtain a `VoltageSequence` from the `VirtualGateSet` instance:
   ```python
   vs = v_gate_set.new_sequence()
   ```
4. **Control Virtual (and Physical) Gates in QUA:** Use `VoltageSequence` methods with virtual gate names, physical gate names, or a mix. The `VirtualGateSet` and `VoltageSequence` will automatically calculate the final physical voltages, summing contributions from all specified levels.

### 5.2 Available VoltageSequence Methods

Since `VirtualGateSet` inherits all features from `GateSet`, you have access to all the same voltage control methods. Here are the key methods you can use:

#### Direct Voltage Control

- `step_to_voltages(voltages: Dict[str, float], duration: int)`  
  Steps channels directly to specified voltage levels. Both `voltages` values and `duration` can be QUA variables.

- `ramp_to_voltages(voltages: Dict[str, float], duration: int, ramp_duration: int)`  
  Ramps channels to specified voltage levels over the ramp duration, then holds. All parameters can be QUA variables.

#### Predefined Tuning Points

- `step_to_point(name: str, duration: Optional[int] = None)`  
  Steps to a predefined `VoltageTuningPoint`. The `duration` parameter can be a QUA variable.

- `ramp_to_point(name: str, ramp_duration: int, duration: Optional[int] = None)`  
  Ramps to a predefined `VoltageTuningPoint`. Both `ramp_duration` and `duration` can be QUA variables.

#### System Control

- `ramp_to_zero(ramp_duration: Optional[int] = None)`  
  Ramps all channels to zero and resets integrated voltage tracking. The `ramp_duration` parameter can be a QUA variable.

- `apply_compensation_pulse(max_voltage: float = 0.49)`  
  Applies compensation pulses to counteract integrated voltage drift (when tracking enabled).

### 5.3 Combining Physical and Virtual Gates

You can seamlessly combine physical and virtual gates in the same operation. The system automatically resolves all contributions and applies them additively to the physical channels.

## 6. Underlying Architecture and Voltage Resolution

### 6.1 How Virtual Gate Resolution Works

When you apply a voltage operation on virtual gates, the system automatically converts this to voltages applied to the underlying physical gates using matrix transformations. Here's how it works:

1. **Matrix-Based Transformation**: Each `VirtualisationLayer` defines a transformation matrix that maps virtual gate voltages to target gate voltages (either physical gates or lower-level virtual gates).

2. **Multi-Layer Resolution**: For multi-layer virtualisation, the system processes layers from the outermost (highest-level virtual gates) to the innermost (physical gates), applying the inverse of each transformation matrix.

3. **Additive Contributions**: All contributions from virtual gates at different layers are summed together at the physical gate level, allowing for complex control schemes.

### 6.2 Core Allocation and Performance

**One core is dedicated to each physical gate**, regardless of the number of virtual gates or virtualisation layers. This has important implications:

- **Scalable Performance**: Adding virtual gates or virtualisation layers doesn't increase the computational load on the QUA system
- **Real-Time Operation**: All matrix calculations are performed at compile time, not during execution
- **Predictable Resource Usage**: The number of cores required is determined solely by the number of physical channels

For example, if you have 3 physical gates (`P1`, `P2`, `P3`) but 10 virtual gates across 3 virtualisation layers, you still only need 3 cores - one for each physical gate.

### 6.3 Matrix Calculation Example

Consider a simple two-layer system:

```python
# Layer 1: Virtual gates to physical gates
matrix_1 = [[1.0, 0.5], [0.5, 1.0]]  # v_Coarse1, v_Coarse2 -> P1, P2

# Layer 2: Higher-level virtual gates to Layer 1 virtual gates
matrix_2 = [[0.1, 0.0], [0.0, 0.1]]  # v_FineTune1, v_FineTune2 -> v_Coarse1, v_Coarse2
```

When you set `v_FineTune1 = 0.1V`, the system:

1. Applies inverse of matrix_2: `v_Coarse1 = 0.1V / 0.1 = 1.0V`
2. Applies inverse of matrix_1: `P1 = 1.0V * 1.0 + 0V * 0.5 = 1.0V`, `P2 = 1.0V * 0.5 + 0V * 1.0 = 0.5V`

This transformation happens at compile time, so the QUA program only sees the final physical gate voltages.

## 7. Relevance to Spin Qubits

Virtual gates are extremely powerful for operating spin qubits:

- **Orthogonal Control:** Provide more orthogonal control over quantum dot properties (e.g., independently tuning inter-dot tunnel coupling and dot chemical potential).
- **Hierarchical Tuning:** Multiple layers allow for a hierarchy of control, from coarse adjustments to fine-tuning.
- **Simplified Tuning:** Complex multi-dimensional tuning tasks become simpler in virtual gate space.
- **Automated Calibration:** Virtual gate matrices can be calibrated automatically, adapting to device changes.
- **Standardization:** Defines device operation in terms of abstract parameters rather than specific physical gate voltages, improving experiment portability and comparability.

The `VirtualGateSet` framework provides the necessary tools to implement these advanced control schemes within QUA.

## 8. Full End to End Example

### 8.1. Create your channels (VoltageGate or SingleChannel)

```python

from quam.components import (
    BasicQuam, 
    StickyChannelAddon, 
    pulses
)
from quam_builder.architecture.quantum_dots import VoltageGate

machine = BasicQuam()

# Define some VoltageGate channels that form your Quam Machine
machine.channels["ch1"] = VoltageGate(
    opx_output=("con1", 1),  # OPX controller and port
    sticky=StickyChannelAddon(duration=1000, digital=False),
    operations={"half_max_square": pulses.SquarePulse(amplitude=0.25, length=1000)},
)
machine.channels["ch2"] = VoltageGate(
    opx_output=("con1", 2),  # OPX controller and port
    sticky=StickyChannelAddon(duration=1000, digital=False),  # For DC offsets
    operations={"half_max_square": pulses.SquarePulse(amplitude=0.25, length=1000)},
)
machine.channels["ch3"] = VoltageGate(
    opx_output=("con1", 3),  # OPX controller and port
    sticky=StickyChannelAddon(duration=100000, digital=False),  # For DC offsets
    operations={"half_max_square": pulses.SquarePulse(amplitude=0.25, length=1000)},
)

```

### 8.2. Create channel dictionary and create your VirtualGateSet

```python

#Ensure that the naming convention is consistent here - "ch1" if it maps to machine.channels["ch1"]
channels = {
    "ch1": machine.channels["ch1"].get_reference(), # .get_reference() necessary to avoid reparenting the Quam component
    "ch2": machine.channels["ch2"].get_reference(),
    "ch3": machine.channels["ch3"].get_reference(),
}

from quam_builder.architecture.quantum_dots import VirtualGateSet  # Requires quam-builder
machine.virtual_gate_set = VirtualGateSet(id = "Plungers", channels = channels)

```

from quam_builder.architecture.quantum_dots.voltage_sequence import VoltageSequence

### 8.3. Add virtual gate layers

```python
machine.virtual_gate_set.add_layer(
    source_gates = ["V1", "V2"], # Pick the virtual gate names here
    target_gates = ["ch1", "ch2"], # Must be a subset of gates in the gate_set
    matrix = [[2,1],[0,1]] # Any example matrix
)
```

### 8.4. Add any relevant tuning points to your GateSet

```python
#Some example points
machine.virtual_gate_set.add_point("init", {"ch1": -0.25, "ch3": 0.12}, duration = 10_000)
machine.virtual_gate_set.add_point("op", {"V1": 0.2, "V2": 0.1}, duration = 1000)
machine.virtual_gate_set.add_point("meas", {"ch3": -0.12}, duration = 3_000)

```

### 8.5. Write QUA program

```python
with program() as prog: 
  my_new_seq = machine.virtual_gate_set.new_sequence(track_integrated_voltage=True)
  my_new_seq.step_to_point("init") # also valid: my_new_seq.step_to_voltages(voltages = {"ch1": -0.25, "ch3": 0.12}, duration = 10_000)
  my_new_seq.step_to_point("op")
  my_new_seq.step_to_point("meas")
```

**What is happening here?**
- In `init`, the input dict is `{"ch1": -0.25, "ch3": 0.12}`. Since ch2 is omitted in this layer, this will internally translate to a full dict of `{"ch1": -0.25, "ch2": 0.0, "ch3": 0.12}`. 

- In `op`, the input dict is comprised of virtual gates `{"V1": 0.2, "V2": 0.1}`. `ch3` is absent, and since `V1` and `V2` map only to `ch1` and `ch2`, `ch3` is interpreted as having an input 0.0, to produce a dict of `{"V1": 0.2, "V2": 0.1, "ch3": 0.0}`. Internally, the physical gate voltages are calculated using the inverse of the virtual gate matrix, to a physical gate dict of `{"ch1": 0.05, "ch2": 0.1, "ch3": 0.0}`. Bear in mind that these voltages are absolute, not relative, despite the sticky elements.

- In `meas`, the input dict is simply `{"ch3": -0.12}`, which is interpreted as `{"ch1": 0.0, "ch2": 0.0, "ch3": -0.12}`. 


