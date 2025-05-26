# GateSet and VoltageSequence: Orchestrating DC Voltage Control in QUA

## 1. Introduction

This guide describes a Python framework for generating QUA sequences to control DC gate voltages, which is particularly useful for spin qubit experiments.
The core components, `GateSet` and `VoltageSequence`, enable precise physical voltage control, essential for quantum dot operations and forming a basis for `VirtualGateSet`.
Users must ensure their QUAM configuration defines necessary base QUA operations for each channel.

## 2. Overview

- `GateSet`: A `QuantumComponent` grouping physical `SingleChannel` objects. It manages named voltage presets (`VoltageTuningPoint` macros) and creates `VoltageSequence` instances.

- `VoltageSequence`: uses the GateSet to apply QUA voltage operations (steps, ramps) within a QUA Program. It tracks channel states, optionally including integrated voltage for DC compensation, which is useful for AC-coupled lines.

**Workflow:**

1.  Define QUAM `SingleChannel` objects for physical gates.

    - This can used from an existing QUAM setup

2.  Ensure each channel has a base QUA operation (e.g., `250mV_square` for a short, 0.25V pulse).

    1.  Will be redundant in a future release

3.  Group channels into a `GateSet`.

4.  Optionally, add `VoltageTuningPoint` macros to the `GateSet`.

5.  Create a `VoltageSequence` from the `GateSet`.

6.  Use `VoltageSequence` methods within a QUA `program()` to define voltage changes.

## 3. `GateSet`

A `GateSet` groups `SingleChannel`s for unified control.

**Key Features:**

- Defines named voltage/duration presets using the `add_point()` method, which internally registers a `VoltageTuningPoint` in `GateSet.macros`.

- `resolve_voltages()`: Ensures all `GateSet` channels have a defined voltage (defaulting to 0.0V if unspecified).

- `new_sequence()`: Creates `VoltageSequence` instances.

**Defining a `GateSet`:**

```
from quam.components import SingleChannel
from quam_builder.architecture.quantum_dots.voltage_sequence import GateSet

# channel_P1, channel_P2 are existing SingleChannel objects

my_gate_set = GateSet(id="dot_plungers", channels={"P1": channel_P1, "P2": channel_P2})

```

While the DC points can be defined dynamically within a program, it may be useful to predefine fixed tuning points, for example the readout point. This can be dded via `my_gate_set.add_point(name="...", voltages={...}, duration=...)`.

```
my_gate_set.add_point(name="idle", voltages={"P1": 0.1, "P2": -0.05}, duration=1000)

```

Internally this adds a **`VoltageTuningPoint` to GateSet.macros**

## 4. `VoltageSequence`

Generates QUA commands for voltage manipulation, associated with a `GateSet`.

**Key Features:**

- Translates high-level requests into QUA `play`, `ramp`, `wait`.

- Tracks current voltage for each channel.

- Optionally tracks integrated voltage for DC compensation (enable via `track_integrated_voltage=True` in `new_sequence()`).

- Supports Python numbers and QUA variables for levels/durations.

**Creating a `VoltageSequence`:**

The sequence must be defined within a QUA program

```
with qua.program() as prog:
voltage_seq = my_gate_set.new_sequence()

```

**Core Methods (used in `qua.program()` context):**

- `step_to_level(levels: Dict, duration)`: Steps specified channels to voltages, holds.

  ```
  voltage_seq.step_to_level(levels={"P1": 0.3, "P2": 0.1}, duration=100)

  ```

- `go_to_point(name: str, duration: Optional[int] = None)`: Steps to a predefined `VoltageTuningPoint`.

  ```
  voltage_seq.go_to_point("idle")

  ```

- `ramp_to_level(levels: Dict, duration, ramp_duration)`: Ramps to voltages, holds.

  ```
  voltage_seq.ramp_to_level(levels={"P1": 0.0}, duration=500, ramp_duration=40)

  ```

- `ramp_to_point(name: str, ramp_duration, duration: Optional = None)`: Ramps to a predefined `VoltageTuningPoint`, holds.

- `ramp_to_zero(ramp_duration_ns: Optional[int] = None)`: Ramps all channels to zero.

- `apply_compensation_pulse(max_voltage: float = 0.49)`: Applies DC compensation (if tracking enabled).

## 5. User Responsibility for QUA Configuration

Each `SingleChannel` in the `GateSet` needs a base QUA operation `250mV_square` which is used by the `VoltageSequence`. This should be defined per channel as

```
from quam.components import pulses

# Assume ch is a singlechannel

ch.operations["250mV_square"] = pulses.SquarePulse(amplitude=0.25, duration=16)
```

## 6. Relevance to Spin Qubits

Precise DC voltage control is vital for:

- Quantum dot formation and tuning.

- Qubit state manipulation (initialization, rotation, readout).

- Maintaining charge stability (DC compensation helps).

## 7. Foundation for Virtual Gates

`GateSet` and `VoltageSequence` provide the physical voltage control layer necessary for `VirtualGateSet`.
A `VirtualGateSet` translates virtual gate operations into physical gate voltage changes, which are then applied using the `VoltageSequence` mechanisms.
