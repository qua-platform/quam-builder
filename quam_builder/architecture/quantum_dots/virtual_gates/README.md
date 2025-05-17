## QUAM-based Voltage Gate Sequencer: Implementation Guide

### 1. Introduction

This document describes a Python framework for generating QUA sequences to control DC voltages on a set of gate channels.
It leverages QUAM (Quantum Orchestration and Measurement) components, specifically `QuantumComponent` and `Channel` objects, to provide a structured way to define and execute complex voltage ramps, steps, and compensation pulses.

The system is designed to be modular, with clear separation of concerns between defining gate sets, managing voltage points, tracking element states, and generating QUA commands.
A key principle is that the user is responsible for ensuring their QUAM configuration correctly defines the necessary base operations for each channel used by this sequencer.
The sequencer classes themselves do _not_ modify the QUA configuration dictionary.

### 2. Overview of the Architecture

The system comprises the following main Python classes:

- **`VoltageTuningPoint(QuamMacro)`**: A data class representing a named set of DC voltage levels for multiple channels, with an associated default duration.
- **`GateSet(QuantumComponent)`**: Represents a collection of QUAM `SingleChannel` objects that will be controlled together. It manages `VoltageTuningPoint` macros.
- **`VoltageSequence`**: The primary class for building a sequence of voltage operations (steps, ramps, compensation) for a given `GateSet`. It uses `SequenceStateTracker` instances to manage the state of each channel.
- **`SequenceStateTracker`** (from `.sequence_state_tracker`): A helper class, instantiated per channel, to track its current voltage level and accumulated integrated voltage (for DC compensation).
- **Helper Modules**:
  - `.exceptions`: Defines custom exceptions like `VoltagePointError`, `TimingError`, `StateError`.
  - `.utils`: Provides utility functions like `is_qua_type` and `validate_duration`.

**Workflow:**

1.  The user defines their experimental setup in a QUAM configuration, including the `QuantumComponent`s for their gates (which will form a `GateSet`) and the individual `SingleChannel`s.
2.  Crucially, for each `SingleChannel` intended for use with this sequencer, the user must define a specific base QUA operation in their configuration (e.g., an operation named `"{channel_id}_vgs_base_op"`). This operation should correspond to a simple pulse of `MIN_PULSE_DURATION_NS` (16ns) with a waveform whose constant sample value is `DEFAULT_BASE_WF_SAMPLE` (0.25V).
3.  The user instantiates a `GateSet` object, providing it with the relevant QUAM `SingleChannel` objects.
4.  Using the `GateSet` instance, the user can define named `VoltageTuningPoint`s via `gate_set.add_point()`.
5.  The user creates a `VoltageSequence` object from the `GateSet` using `gate_set.new_sequence()`.
6.  Within a QUA `program()` context, the user calls methods on the `VoltageSequence` object (e.g., `go_to_point()`, `step_to_level()`, `apply_compensation_pulse()`, `ramp_to_zero()`) to build the desired sequence of voltage changes.

### 3. Class Descriptions

#### 3.1. `VoltageTuningPoint(QuamMacro)`

- **Purpose**: Represents a specific, named configuration of DC voltages for the channels in a `GateSet`, along with a default duration.
- **Key Attributes**:
  - `voltages: Dict[str, float]`: Maps channel names (which must be keys in the parent `GateSet.channels`) to their target DC voltage for this point.
  - `duration: int`: The default duration (in nanoseconds) to hold these voltages when this point is targeted.
- **Usage**: Defined via `GateSet.add_point()` and stored in `GateSet.macros`. Referenced by name in `VoltageSequence.go_to_point()` and `VoltageSequence.ramp_to_point()`.

#### 3.2. `GateSet(QuantumComponent)`

- **Purpose**: Represents a logical grouping of QUAM `SingleChannel` objects that are to be controlled as a cohesive unit for voltage sequencing. It acts as a factory for `VoltageSequence` objects and a container for `VoltageTuningPoint` macros relevant to this set of channels.
- **Key Attributes**:
  - `channels: Dict[str, SingleChannel]`: A dictionary mapping user-defined names to the QUAM `SingleChannel` instances that form this gate set.
  - `macros: Dict[str, QuamMacro]`: Inherited from `QuantumComponent`, used to store `VoltageTuningPoint` instances.
- **Key Methods**:
  - `__init__(self, channels: Dict[str, SingleChannel], **kwargs)`: Initializes the gate set with its channels.
  - `add_point(self, name: str, voltages: Dict[str, float], duration: int)`: Creates and registers a `VoltageTuningPoint`.
  - `new_sequence(self) -> VoltageSequence`: Factory method to create a `VoltageSequence` instance bound to this `GateSet`.
- **Dependencies**: `SingleChannel`, `VoltageTuningPoint`, `VoltageSequence` (for type hint in `new_sequence`).

#### 3.3. `SequenceStateTracker` (from `.sequence_state_tracker`)

- **Purpose**: Tracks the real-time state (current voltage and accumulated integrated voltage) of a single gate channel. It handles transitions between Python numeric state and QUA variable state when necessary.
- **Key Attributes (Properties)**:
  - `element_name: str`: The name of the channel this tracker is for.
  - `current_level: VoltageLevelType`: The last set voltage level for the channel.
  - `integrated_voltage: Union[int, QuaVariable]`: The accumulated `voltage * duration * scale_factor`, used for DC compensation.
- **Key Methods**:
  - `__init__(self, element_name: str)`: Initializes state for the given element.
  - `update_integrated_voltage(self, level: VoltageLevelType, duration: DurationType, ramp_duration: Optional[DurationType] = None)`: Updates the integrated voltage based on a pulse segment.
  - `reset_integrated_voltage(self)`: Resets the integrated voltage to zero.
- **Dependencies**: QUA types (`QuaVariable`, `QuaExpression`), `is_qua_type` (from `.utils`), `StateError` (from `.exceptions`).

#### 3.4. `VoltageSequence`

- **Purpose**: The main user-facing class for constructing a sequence of voltage operations within a QUA program. It orchestrates state tracking and QUA command generation for all channels in its associated `GateSet`.
- **Key Attributes**:
  - `gate_set: GateSet`: The `GateSet` this sequence operates upon.
  - `state_trackers: Dict[str, SequenceStateTracker]`: A dictionary mapping channel names to their respective `SequenceStateTracker` instances.
  - `_temp_qua_vars: Dict[str, QuaVariable]`: Internal storage for temporary QUA variables needed for calculations (e.g., ramp rates).
- **Key Methods**:
  - `__init__(self, gate_set: GateSet)`: Initializes the sequence with a `GateSet` and creates trackers for each channel.
  - `step_to_level(self, levels: Dict[str, VoltageLevelType], duration: DurationType)`: Steps specified channels to defined voltage levels.
  - `ramp_to_level(self, levels: Dict[str, VoltageLevelType], duration: DurationType, ramp_duration: DurationType)`: Ramps specified channels to defined voltage levels, then holds.
  - `go_to_point(self, name: str, duration: Optional[int] = None)`: Steps all channels to the voltages defined in a named `VoltageTuningPoint`.
  - `ramp_to_point(self, name: str, ramp_duration: DurationType, duration: Optional[DurationType] = None)`: Ramps all channels to the voltages of a named `VoltageTuningPoint`, then holds.
  - `apply_compensation_pulse(self, max_voltage: float = 0.49)`: Applies DC compensation pulses to all channels.
  - `ramp_to_zero(self, ramp_duration_ns: Optional[int] = None)`: Ramps all channel voltages to zero and resets their integrated voltage tracking.
  - `apply_to_config(self, config: dict)`: (Placeholder) Intended for future validation or guidance regarding the user's QUA configuration. Does not modify the config.
- **Dependencies**: `GateSet`, `SequenceStateTracker`, `VoltageTuningPoint`, QUA functions, helper utilities from `.utils`, and exceptions from `.exceptions`.

### 4. Workflow and Dependencies Summary

```mermaid
graph TD
    A[User Defines QUAM Config] --> B(Instantiates QUAM SingleChannel Objects);
    B --> C(Instantiates GateSet with Channels);
    C -- add_point() --> D[Defines VoltageTuningPoint Macros];
    C -- new_sequence() --> E(Creates VoltageSequence Object);
    E --> F[Operates within QUA program context];
    F -- Uses methods --> G{go_to_point, step_to_level, etc.};
    E -- Manages --> H(SequenceStateTracker Instances per Channel);

    subgraph "User Responsibility"
        A
    end

    subgraph "Framework Classes"
        C
        D
        E
        H
    end

    subgraph "QUA Environment"
        F
        G
    end

    note for A "User must ensure base operations (e.g., '{channel_id}_vgs_base_op') are defined for each channel."
```

### 5. Code Examples

**Prerequisites:**
Ensure your QUAM environment is set up, and you have the necessary modules:

- `sequence_state_tracker.py` (containing `SequenceStateTracker`)
- `exceptions.py` (containing `VoltagePointError`, `TimingError`, etc.)
- `utils.py` (containing `is_qua_type`, `validate_duration`)

**Example 1: Initialization and Defining Points**

```python
# --- Assuming QUAM imports and other classes are available ---
# from quam.components.channels import SingleChannel
# from quam.components import QuantumComponent
# from your_module import GateSet, VoltageTuningPoint, VoltageSequence # etc.

# 1. Define your QUAM Channels (typically loaded from a larger QUAM config)
# For this example, let's assume they are already instantiated:
channel_P1 = SingleChannel(id="P1_gate") # User ensures "P1_gate_vgs_base_op" exists in config
channel_P2 = SingleChannel(id="P2_gate") # User ensures "P2_gate_vgs_base_op" exists in config

# 2. Create a GateSet
# Assuming GateSet is a QuantumComponent, it might also take an 'id'
my_gate_set = GateSet(id="dot_gates", channels={
    "P1": channel_P1,
    "P2": channel_P2
})

# 3. Add Voltage Tuning Points to the GateSet
my_gate_set.add_point(
    name="idle",
    voltages={"P1": -0.1, "P2": 0.05}, # Voltages for P1 and P2 channels
    duration=1000  # ns
)
my_gate_set.add_point(
    name="load_dot",
    voltages={"P1": 0.2, "P2": -0.1},
    duration=200
)

# 4. Create a VoltageSequence from the GateSet
# This sequence object will be used inside the QUA program
seq = my_gate_set.new_sequence()
```

**Example 2: Using VoltageSequence in a QUA Program**

```python
from qm.qua import program, declare, fixed, align

# ... (setup from Example 1: channel_P1, channel_P2, my_gate_set, seq) ...

with program() as my_voltage_program:
    # Declare QUA variables if needed for dynamic levels/durations
    target_p1_level = declare(fixed, value=0.15)
    custom_ramp_duration = declare(int, value=40) # ns

    # Go to a predefined point (direct step)
    seq.go_to_point("idle") # Uses duration from "idle" point (1000ns)

    # Ramp to another predefined point, then hold for its default duration
    seq.ramp_to_point("load_dot", ramp_duration=custom_ramp_duration)

    # Step directly to specified levels for a given duration
    seq.step_to_level(
        levels={"P1": target_p1_level, "P2": 0.0},
        duration=500 # ns
    )

    # Ramp to specified levels, hold for a duration
    seq.ramp_to_level(
        levels={"P1": 0.0, "P2": 0.0},
        duration=100, # ns (hold duration)
        ramp_duration=20 # ns (ramp duration)
    )

    # Apply compensation pulse
    # This assumes some operations have occurred that shifted the DC average
    seq.apply_compensation_pulse(max_voltage=0.45)

    # Align with other operations if necessary
    align()

    # Ramp all gate voltages in the set to zero
    seq.ramp_to_zero(ramp_duration_ns=100) # Ramp over 100ns

# At this point, 'my_voltage_program' contains the QUA program.
# The user's main QUA configuration (which defines "P1_gate_vgs_base_op", etc.)
# would be passed to the QuantumMachinesManager along with this program.
# The VoltageSequence object itself does not hold or return the config.
# seq.apply_to_config(my_actual_qua_config) # Can be called for guidance/validation
```

**User Responsibility for QUA Configuration:**

It is critical that the user's main QUA configuration dictionary correctly defines a base operation for each `SingleChannel` ID used in the `GateSet`.
For a channel with ID `my_channel_id`, the sequencer expects:

1.  An **operation** named `my_channel_id_vgs_base_op`.
2.  This operation must point to a **pulse**, e.g., `my_channel_id_vgs_base_pulse`.
3.  This pulse must have a defined `length` of `MIN_PULSE_DURATION_NS` (e.g., 16 ns).
4.  This pulse must use a **waveform**, e.g., `my_channel_id_vgs_base_wf`.
5.  This waveform must be of `type: "constant"` and have a `sample` value of `DEFAULT_BASE_WF_SAMPLE` (e.g., 0.25 V).

Example entry in the QUA `config["elements"]`:

```json
"P1_gate": {
    // ... other P1_gate configurations ...
    "operations": {
        "P1_gate_vgs_base_op": "P1_gate_vgs_base_pulse"
        // ... other operations ...
    }
}
```

And in `config["pulses"]` and `config["waveforms"]`:

```json
"P1_gate_vgs_base_pulse": {
    "operation": "control",
    "length": 16, // MIN_PULSE_DURATION_NS
    "waveforms": {
        "single": "P1_gate_vgs_base_wf"
    }
},
"P1_gate_vgs_base_wf": {
    "type": "constant",
    "sample": 0.25 // DEFAULT_BASE_WF_SAMPLE
}
```

### 6. Conclusion

This QUAM-based voltage sequencing framework provides a structured and Pythonic way to generate complex DC voltage sequences for gate control. By leveraging QUAM components and separating concerns, it aims for clarity and maintainability, while giving the user full control over their QUA configuration.
