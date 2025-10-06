# VoltageSequence: Orchestrating DC Voltage Control in QUA

NOTE: This document is a brief intro into `GateSet` and `VoltageSequence`, not a full guide. For a more thorough guide on `GateSet`, `VoltageSequence` and `VirtualGateSet`, please refer to the [quantum_dots README](../../architecture/quantum_dots/README.md). 

## 1. Introduction

This document describes a Python framework for generating QUA sequences to control DC gate voltages, which is particularly useful for spin qubit experiments.
The core components, `GateSet` and `VoltageSequence`, enable precise physical voltage control, essential for quantum dot operations and forming a basis for `VirtualGateSet`.
This framework is specifically designed to work with channels that have **sticky mode enabled**, which is common in quantum dot experiments because any gaps in the pulse sequence maintain a steady voltage level.

## 2. Overview and Workflow

- `GateSet`: A `QuantumComponent` grouping physical `VoltageGate` objects. It manages named voltage presets (`VoltageTuningPoint` macros) and creates `VoltageSequence` instances.

- `VoltageSequence`: uses the GateSet to apply QUA voltage operations (steps, ramps) within a QUA Program. It tracks channel states, optionally including integrated voltage for DC compensation, which is useful for AC-coupled lines. **One of its primary features is that it keeps track of the current voltage on each channel, allowing you to ramp to absolute voltages even with sticky mode enabled.**

### 2.1 **Workflow:**

- **This README will start with an end-to-end example before delving into the specifics. This example workflow takes place in 6 broad steps:**

#### 1.  Define QUAM `VoltageGate` objects for physical gates

- A `VoltageGate` channel is a Quantum Dot specific channel inheriting from QuAM's `SingleChannel` object. It adds to the `SingleChannel` by containing an `offset_parameter` and an `attenuation` value. 

- Below is an example of how a `VoltageGate` is instantiated. 

  ```python
  from quam_builder.architecture.quantum_dots.components import VoltageGate
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

- Each channel should have a base QUA operation named `"half_max_square"`, as shown above. Note that `GateSet.new_sequence()` automatically updates the channel operations to include `"half_max_square"`; ensure that the config is generated, and the QM is opened only afterwards.



#### 2.  Group channels into a channel dictionary

  ```python
  channels = {
    "channel_p1": channel_p1,
    "channel_p2": channel_p2,
  }
  ```

- It is important to ensure that the string names used here match the string names in your QuAM machine

- If your channel object are already parented by a QuAM machine (i.e. `machine.channel["channel_p1"] = VoltageGate(...)`), then the channels cannot be re-parented into your GateSet. In this case, it is important to use the channel reference as such: 

  ```python
  channels = {
    "channel_p1": channel_p1.get_reference(),
    "channel_p2": channel_p2.get_reference()
  }
  ```

#### 3.  Instantiate your GateSet with your channel mapping

  ```python 
  from quam_builder.architecture.quantum_dots.components import GateSet

  my_gate_set = GateSet(id="dot_plungers", channels=channels)
  ```

#### 4.  Optionally, add `VoltageTuningPoint` macros to the `GateSet`
    
- This is useful for when you have set points in your charge-stability that must be re-used in the experiment. GateSet can hold VoltageTuningPoints which can easily be accessed by VoltageSequence

  ```python
  my_gate_set.add_point(name="idle", voltages={"channel_P1": 0.1, "channel_P2": -0.05}, duration=1000)
  ```
    
    Internally this adds a **`VoltageTuningPoint` to GateSet.macros**

#### 5.  Create a `VoltageSequence` from the `GateSet`

  ```python 
  voltage_seq = my_gate_set.new_sequence()
  ```

- `voltage_seq` can be used in QUA programs to easily step/ramp to points. 

#### 6.  Use `VoltageSequence` methods within a QUA `program()` to define voltage changes

- Remember: The sequence must be defined inside the QUA program.

  ```python
  with qua.program() as prog:
      voltage_seq = my_gate_set.new_sequence()
      voltage_seq.step_to_point("idle") # Step to point "idle". ramp_to_point also valid, with a ramp_duration argument. 
      voltage_seq.step_to_voltages(voltages = {...}, duration = ...) # In-case you would like to step to a point not saved as a macro in the GateSet, you can just define it here
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
