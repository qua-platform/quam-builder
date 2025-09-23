# GateSet & VirtualGateSet: Orchestrating DC Voltage Control in QUA & Abstracting Gate Control with Virtualisation Layers

## 1. Introduction

This document first introduces the **GateSet** component with the **VoltageSequence** tool, a python framework for generating QUA sequences to group control of DC gate voltages, particularly useful for spin qubit experiments. 

The components `GateSet` and `VoltageSequence` enable precise physical voltage control, essential for quantum dot operations and forming a basis for `VirtualGateSet`.

Spin qubit experiments are encouraged to use the **VoltageGate** QuAM channel. A `VoltageGate` channel is a Quantum Dot specific channel inheriting from QuAM's `SingleChannel` object. It adds to the `SingleChannel` by containing an `offset_parameter` and an `attenuation` value. 

Subsequently, this document introduces the **VirtualGateSet** and **VirtualisationLayer** components. These extend the physical gate control capabilities provided by `GateSet` and `VoltageSequence` by adding one or more layers of virtual gates.

Virtual gates simplify complex tuning procedures in experiments, especially for spin qubits, by allowing control over abstract parameters that map to multiple physical gate voltages.

**`VirtualGateSet` builds upon `GateSet` and inherits all of its features**, including physical channel management, `VoltageTuningPoint` definitions, and all voltage control methods. This means you can use virtual gates while still having access to all the voltage control capabilities of the underlying `GateSet`.

## 2. Overview and Workflow

### 2.1. Components Overview

#### 2.1.1 GateSet

`GateSet` is a `QuantumComponent` grouping physical `VoltageGate` (and thus `SingleChannel`) objects. It manages named voltage presets (`VoltageTuningPoint` macros) and creates `VoltageSequence` instances.

#### 2.1.2 VoltageSequence

`VoltageSequence` uses the GateSet to apply QUA voltage operations (steps, ramps) within a QUA Program. It tracks channel states, optionally including integrated voltage for DC compensation, which is useful for AC-coupled lines. **One of its primary features is that it keeps track of the current voltage on each channel, allowing you to ramp to absolute voltages even with sticky mode enabled.**

#### 2.1.3 VirtualGateSet

A subclass of `GateSet`. It manages a list of `VirtualisationLayer` objects, which define the transformations from virtual gate voltages to underlying (either physical or lower-level virtual) gate voltages.

#### 2.1.4 VirtualisationLayer

Represents a single linear transformation (matrix) from a set of source (virtual) gates to a set of target gates.

#### 2.1.5 VoltageGate

`VoltageGate` is a QuAM channel built specifically to handle quantum dot and spin qubit experiments. It inherits from `SingleChannel`, adding an `offset_parameter` and `attenuation` values. 

### 2.2 Workflow

**This document will start with an end-to-end example before diving into the specifics. This example workflow takes place in 7 broad steps:**

#### 1.  Define QUAM `VoltageGate` objects for physical gates

- Below is an example of how a `VoltageGate` is instantiated. As appropriate, add `offset_parameter` and `attenuation` arguments. 

  ```python
  from quam_builder.architecture.quantum_dots import VoltageGate
  from quam.components import StickyChannelAddon, pulses


  channel_p1 = VoltageGate(
    opx_output = ("con1", 1), #Specify the OPX output
    sticky=StickyChannelAddon(duration=1_000, digital=False),  # For DC offsets
    operations={"half_max_square": pulses.SquarePulse(amplitude=0.25, length=1000)},
  )


  channel_p2 = VoltageGate(
    opx_output = ("con1", 2), #Specify the OPX output
    sticky=StickyChannelAddon(duration=1_000, digital=False),  # For DC offsets
    operations={"half_max_square": pulses.SquarePulse(amplitude=0.25, length=1000)},
  )
  ```

#### 2.  Ensure each channel has a base QUA operation (e.g., `half_max_square` for a short, 0.25V pulse)

- This will be redundant in a future release.

- This has already been done in step 1. Notice the `operations` input has a default operation named `"half_max_square"`. 

- NOTE: `GateSet.new_sequence()` automatically updates the channel operations to include `"half_max_square"`; ensure that the config is generated, and the QM is opened only afterwards.


#### 3.  Group channels into a channel dictionary

  ```python
  channels = {
    "channel_p1": channel_p1,
    "channel_p2": channel_p2,
  }
  ```

- When creating this mapping, it is important to ensure that the string names used here match the string names in your QuAM machine.

- If your channel object are already parented by a QuAM machine (i.e. `machine.channel["channel_p1"] = VoltageGate(...)`), then the channels cannot be re-parented into your GateSet. In this case, it is important to use the channel reference as such: 

  ```python
  channels = {
    "channel_p1": channel_p1.get_reference(),
    "channel_p2": channel_p2.get_reference()
  }
  ```


#### 4.  Instantiate your GateSet with your channel mapping

- Below shows an example of instantiating your `GateSet`, for basic group control of `VoltageGate` channels. 

  ```python 
  from quam_builder.architecture.quantum_dots import GateSet

  my_gate_set = GateSet(id="dot_plungers", channels=channels)
  ```

- If virtual gates are necessary in your setup, use the `VirtualGateSet` instead. The instantiation of `VirtualGateSet` is identical to the `GateSet`. 

  ```python
  from quam_builder.architecture.quantum_dots import VirtualGateSet

  my_virtual_gate_set = VirtualGateSet(id="dot_plungers", channels=channels)

  ```

##### 4.1 (Optional) Add Virtualisation Layers 

- If you are using the `VirtualGateSet`, you can map virtualisation layers onto your existing physical or virtual gates using the `.add_layer()` method. You must name the new virtual `source_gates` and input a transformation matrix. This does not need to map onto all of your existing physical or virtual gates. 

  ```python
  # Add coarse tuning layer (virtual gates for overall dot positions)
  my_virtual_gate_set.add_layer(
      source_gates=["v_Coarse1", "v_Coarse2"],
      target_gates=["channel_p1", "channel_p2"], #Your existing physical gates should be the target_gates of your first layer
      matrix=[[1.0, 0.5], [0.5, 1.0]]  # Coupled control
  )

  # Add fine tuning layer (virtual gates for precise adjustments)
  my_virtual_gate_set.add_layer(
      source_gates=["v_FineTune1", "v_FineTune2"],
      target_gates=["v_Coarse1", "v_Coarse2"],
      matrix=[[0.1, 0.0], [0.0, 0.1]]  # Small adjustments
  )
  ```

#### 5.  Add `VoltageTuningPoint` macros to the `GateSet` or `VirtualGateSet`
    
- This is useful for when you have set points in your charge-stability that must be re-used in the experiment. GateSet can hold VoltageTuningPoints which can easily be accessed by VoltageSequence

  ```python
  my_gate_set.add_point(name="idle", voltages={"channel_P1": 0.1, "channel_P2": -0.05}, duration=1000)
  ```
    
- Internally this adds a **`VoltageTuningPoint` to GateSet.macros**

- This is not unique to `GateSet`, or indeed physical gates. `VirtualGateSet` is capable of holding virtual tuning points. The input dictionary mapping can contain any combination of physical or virtual gates, from any layer in the `VirtualGateSet`. The exact mechanism with which the output voltage is calculated is covered later. 

  ```python
  my_virtual_gate_set.add_point(name="idle", voltages={"v_FineTune1": 0.1, "v_Coarse2": -0.05}, duration=1000)
  ```

#### 6.  Create a `VoltageSequence` from the `GateSet` or `VirtualGateSet` inside your QUA programme

- `voltage_seq` in the below example can be used in QUA programs to easily step/ramp to points defined as macros in your `GateSet` or `VirtualGateSet`

  ```python 
  with program() as basic_control: 
    voltage_seq = my_gate_set.new_sequence()
  ```

- Or, if using the `VirtualGateSet`, 

  ```python 
  with program() as complex_control: 
    voltage_seq = my_virtual_gate_set.new_sequence()
  ```

#### 7. Create your QUA program with your `VoltageSequence`

- Instantiate your new sequence in the QUA programme, and step/ramp to any point.

- For a basic `GateSet`, 

  ```python
  with qua.program() as basic_control:
      voltage_seq = my_gate_set.new_sequence()
      voltage_seq.step_to_point("idle") # Step to pre-defined point "idle". ramp_to_point also valid, with a ramp_duration argument, also shown in the VirtualGateSet example
      voltage_seq.step_to_voltages(voltages = {...}, duration = ...) # In-case you would like to step to a point not saved as a macro in the GateSet, you can just define it here
  ```

- Use a `VirtualGateSet` for full control over virtual and physical points:

  ```python
  # Create voltage sequence
  with qua.program() as complex_control:
      voltage_seq = my_virtual_gate_set.new_sequence()

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
              "channel_p2": 0.3              # Direct physical gate control
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

## 3. `GateSet`

A `GateSet` is a higher-level abstraction that collects a group of `VoltageGate` or `SingleChannel` channels and treats them as a single, coordinated object for unified control. This is especially useful in Quantum Dot architectures, where one often has many physical gate electrodes that must be tuned together. Instead of controlling each `VoltageGate`/`SingleChannel` channel in isolation, the GateSet allows 

- Unified control: Iterate, configure, and programme multiple gates at once through a single object 

- Pre-defined DC points: Store named DC working points using add_point(...)

- Voltage Sequences: Used in conjunction with VoltageSequence, a Sequence created in the GateSet allows you to quickly apply complex QUA commands to groups of gates, as well as keeping track of the gate voltages such that a compensating pulse can be applied later.

**Key Features:**

- Defines named voltage/duration presets using the `add_point()` method, which internally registers a `VoltageTuningPoint` in `GateSet.macros`.

- `resolve_voltages()`: Ensures all `GateSet` channels have a defined voltage (defaulting to 0.0V if unspecified). This is particularly useful when you want to specify voltages for only a subset of channels while ensuring all other channels have defined values.

  **Example:**

  ```python
  # Assume gate_set has channels: {"P1": channel_P1, "P2": channel_P2, "B1": channel_B1}

  # Only specify the voltages of a partial subset of all the gates in the GateSet. 
  partial_voltages = {"P1": 0.3, "B1": -0.1}

  # resolve_voltages fills in missing channels, creating a complete voltages dict internally by replacing all the un-named gate voltages with 0.0V
  complete_voltages = gate_set.resolve_voltages(partial_voltages)
  # Result: {"P1": 0.3, "P2": 0.0, "B1": -0.1}
  ```

- `new_sequence()`: Creates `VoltageSequence` instances.

- While the tuning points can be defined dynamically within a program, it may be useful to predefine fixed tuning points, for example the readout point. This can be dded via `my_gate_set.add_point(name="...", voltages={...}, duration=...)`.

- Internally this adds a **`VoltageTuningPoint` to GateSet.macros**

## 4. `VoltageSequence`

Generates QUA commands for voltage manipulation, associated with a `GateSet`.

**Key Features:**

- Translates high-level requests into QUA `play`, `ramp`, `wait`.

- Tracks current voltage for each channel.

- Optionally tracks integrated voltage for DC compensation (enable via `track_integrated_voltage=True` in `new_sequence()`).

- Supports Python numbers and QUA variables for levels/durations.

### Important Behavior (Zeroing Semantics)

- Any channels unspecified in the input voltages dict are treated as 0 V on each call (consistent with `GateSet.resolve_voltages`).
- When the sequence is created from a `VirtualGateSet`, any virtual gate not included in a call is assumed 0 V for that operation. This clears any previous contribution from that virtual gate in the resolved physical voltages.

Implication: virtual gates do not maintain state across calls. To preserve a virtual configuration, always include all relevant virtual gates (and their values) in each `step_to_voltages`/`ramp_to_voltages` call, or operate directly on physical gates.

- NOTE: When using QUA loops (such as for_, or infinite_loop_) bear in mind that the internal voltage tracker can not track voltages past the first loop. As such, ensure that the start and end point of the loop of the elements are identical

**Creating a `VoltageSequence`:**

- The sequence must be defined within a QUA program. 


**Core Methods (used in `qua.program()` context):**

- `step_to_voltages(voltages: Dict[str, float], duration: int)`  
  Steps all specified channels directly to the given voltage levels and holds them for the specified duration (in nanoseconds). This creates immediate voltage changes without ramping. Both `voltages` values and `duration` can be QUA variables for dynamic control.

  ```python
  voltage_seq.step_to_voltages(voltages={"P1": 0.3, "P2": 0.1}, duration=1000)
  ```

- `ramp_to_voltages(voltages: Dict[str, float], duration: int, ramp_duration: int)`  
  Ramps all specified channels to the given voltage levels over the specified ramp duration, then holds them for the duration (both in nanoseconds). This provides smooth voltage transitions useful for avoiding voltage spikes that could affect sensitive quantum systems. All parameters can be QUA variables.

  ```python
  voltage_seq.ramp_to_voltages(voltages={"P1": 0.0}, duration=500, ramp_duration=40)
  ```

- `step_to_point(name: str, duration: Optional[int] = None)`  
  Steps all channels to the voltages defined in a predefined `VoltageTuningPoint` macro. If no duration is provided, uses the default duration from the tuning point definition. This enables quick transitions to well-defined system states. The `duration` parameter can be a QUA variable.

  ```python
  voltage_seq.step_to_point("idle")
  voltage_seq.step_to_point("readout", duration=2000)  # Override default duration
  ```

- `ramp_to_point(name: str, ramp_duration: int, duration: Optional[int] = None)`  
  Ramps all channels to the voltages defined in a predefined `VoltageTuningPoint` over the specified ramp duration, then holds them. Combines the smooth transitions of ramping with the convenience of predefined voltage states. Both `ramp_duration` and `duration` can be QUA variables.

  ```python
  voltage_seq.ramp_to_point("idle", ramp_duration=50, duration=1000)
  ```

- `ramp_to_zero(ramp_duration: Optional[int] = None)`  
  Ramps the voltage on all channels in the GateSet to zero and resets the integrated voltage tracking for each channel. If no duration is specified, uses QUA's built-in `ramp_to_zero` command for immediate ramping. Essential for safely returning to a neutral state. The `ramp_duration` parameter can be a QUA variable.

  ```python
  voltage_seq.ramp_to_zero()  # Immediate ramp using QUA built-in
  voltage_seq.ramp_to_zero(ramp_duration=100)  # Controlled ramp over 100ns
  ```

- `apply_compensation_pulse(max_voltage: float = 0.49)`  
  Applies a compensation pulse to each channel to counteract integrated voltage drift when tracking is enabled. The compensation amplitude is calculated based on the accumulated integrated voltage, with the pulse duration optimized to stay within the specified maximum voltage limit. Only available when `track_integrated_voltage=True`.

  ```python
  voltage_seq.apply_compensation_pulse()  # Use default 0.49V limit
  voltage_seq.apply_compensation_pulse(max_voltage=0.3)  # Custom voltage limit
  ```

## 5. Foundation for Virtual Gates

`GateSet` and `VoltageSequence` provide the physical voltage control layer necessary for `VirtualGateSet`.
A `VirtualGateSet` translates virtual gate operations into physical gate voltage changes, which are then applied using the `VoltageSequence` mechanisms.


## 6. VirtualGateSet

A `VirtualGateSet` allows users to define and operate with virtual gates, abstracting the underlying physical gate operations.

**Key Features:**

- **Inherits from `GateSet`:** Retains all functionalities of `GateSet`, including physical channel management and `VoltageTuningPoint` definitions.
- **Manage Multiple Virtualisation Layers:** Stores a list of `VirtualisationLayer` objects. Multiple layers can be defined and stacked, allowing for hierarchical virtualisation. Layers are applied sequentially (in reverse order during voltage resolution) to translate top-level virtual gate voltages into physical gate voltages.
- **Add Layers:** Use `add_layer(source_gates, target_gates, matrix)` to define and append a new `VirtualisationLayer`:
  - `source_gates`: Names of the new virtual gates defined by this layer.
  - `target_gates`: Names of the gates (physical or virtual from a previous layer) that this layer maps onto.
  - `matrix`: The transformation matrix (list of lists of floats).
- **Additive Voltage Resolution:** Overrides `GateSet.resolve_voltages()`. When voltages are specified for virtual gates (potentially across different layers) and/or physical gates simultaneously, this method applies the inverse of the virtualisation matrices for each layer. Contributions from all specified virtual and physical gates are resolved and become additive at the physical gate level. Handles multi-layered virtualisation by processing layers from the outermost to the innermost.

### 6.1 Important Behavior: Unspecified Virtual Gates Are Zeroed Per Operation

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


## 7. VirtualisationLayer

A `VirtualisationLayer` defines a single step in the virtual-to-physical gate voltage transformation.

**Key Attributes:**

- `source_gates` (`List[str]`): Names of the virtual gates defined in this layer.
- `target_gates` (`List[str]`): Names of the physical or underlying virtual gates this layer maps to.
- `matrix` (`List[List[float]]`): The virtualisation matrix defining the linear transformation. The relationship is `V_source = M * V_target`. When resolving, `V_target = M_inverse * V_source` is used for this layer's contribution.
- Handles the calculation of the inverse matrix and the resolution of voltages for its specific layer.

### Mathematical Relations

### 7.1 Forward Transformation (Virtual to Physical)

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

### 7.2 Inverse Transformation (Voltage Resolution)

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

### 7.3 Multi-Layer Resolution

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

### 7.4 Additive Voltage Contributions

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

### 7.5 Matrix Constraints

For a valid virtualisation layer:

- Matrix must be square: `len(source_gates) == len(target_gates)`
- Matrix must be invertible (non-singular): `det(M) ≠ 0`
- The inverse matrix is calculated using `numpy.linalg.inv(matrix)`


## 8. Workflow and Usage

### 8.1 Broad Steps

1. **Initialize `VirtualGateSet`:** Create an instance with the physical `SingleChannel` objects.
2. **Add Layers:** Use `v_gate_set.add_layer()` to define each virtualisation matrix. Multiple layers can be stacked.
3. **Create `VoltageSequence`:** Obtain a `VoltageSequence` from the `VirtualGateSet` instance:
   ```python
   vs = v_gate_set.new_sequence()
   ```
4. **Control Virtual (and Physical) Gates in QUA:** Use `VoltageSequence` methods with virtual gate names, physical gate names, or a mix. The `VirtualGateSet` and `VoltageSequence` will automatically calculate the final physical voltages, summing contributions from all specified levels.

### 8.2 Available VoltageSequence Methods

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

### 8.3 Combining Physical and Virtual Gates

You can seamlessly combine physical and virtual gates in the same operation. The system automatically resolves all contributions and applies them additively to the physical channels.

## 9. Underlying Architecture and Voltage Resolution

### 9.1 How Virtual Gate Resolution Works

When you apply a voltage operation on virtual gates, the system automatically converts this to voltages applied to the underlying physical gates using matrix transformations. Here's how it works:

1. **Matrix-Based Transformation**: Each `VirtualisationLayer` defines a transformation matrix that maps virtual gate voltages to target gate voltages (either physical gates or lower-level virtual gates).

2. **Multi-Layer Resolution**: For multi-layer virtualisation, the system processes layers from the outermost (highest-level virtual gates) to the innermost (physical gates), applying the inverse of each transformation matrix.

3. **Additive Contributions**: All contributions from virtual gates at different layers are summed together at the physical gate level, allowing for complex control schemes.

### 9.2 Core Allocation and Performance

**One core is dedicated to each physical gate**, regardless of the number of virtual gates or virtualisation layers. This has important implications:

- **Scalable Performance**: Adding virtual gates or virtualisation layers doesn't increase the computational load on the QUA system
- **Real-Time Operation**: All matrix calculations are performed at compile time, not during execution
- **Predictable Resource Usage**: The number of cores required is determined solely by the number of physical channels

For example, if you have 3 physical gates (`P1`, `P2`, `P3`) but 10 virtual gates across 3 virtualisation layers, you still only need 3 cores - one for each physical gate.

### 9.3 Matrix Calculation Example

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

## 10. Relevance to Spin Qubits

Virtual gates are extremely powerful for operating spin qubits:

- **Orthogonal Control:** Provide more orthogonal control over quantum dot properties (e.g., independently tuning inter-dot tunnel coupling and dot chemical potential).
- **Hierarchical Tuning:** Multiple layers allow for a hierarchy of control, from coarse adjustments to fine-tuning.
- **Simplified Tuning:** Complex multi-dimensional tuning tasks become simpler in virtual gate space.
- **Automated Calibration:** Virtual gate matrices can be calibrated automatically, adapting to device changes.
- **Standardization:** Defines device operation in terms of abstract parameters rather than specific physical gate voltages, improving experiment portability and comparability.

The `VirtualGateSet` framework provides the necessary tools to implement these advanced control schemes within QUA.

## 11. Full End to End Example

### 11.1. Create your channels (VoltageGate or SingleChannel)

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

### 11.2. Create channel dictionary and create your VirtualGateSet

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

### 11.3. Add virtual gate layers

```python
machine.virtual_gate_set.add_layer(
    source_gates = ["V1", "V2"], # Pick the virtual gate names here
    target_gates = ["ch1", "ch2"], # Must be a subset of gates in the gate_set
    matrix = [[2,1],[0,1]] # Any example matrix
)
```

### 11.4. Add any relevant tuning points to your GateSet

```python
#Some example points
machine.virtual_gate_set.add_point("init", {"ch1": -0.25, "ch3": 0.12}, duration = 10_000)
machine.virtual_gate_set.add_point("op", {"V1": 0.2, "V2": 0.1}, duration = 1000)
machine.virtual_gate_set.add_point("meas", {"ch3": -0.12}, duration = 3_000)

```

### 11.5. Write QUA program

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


