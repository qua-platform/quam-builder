# Voltage Point Macro System

This directory contains the voltage point macro functionality for quantum dot components, providing a powerful and flexible system for controlling voltages in quantum computing experiments.

## Overview

The voltage point macro system consists of two main components:

1. **`SequenceMacro`**: A callable class that encapsulates voltage operations (ramp or step) to pre-defined voltage points
2. **`VoltagePointMacroMixin`**: A mixin class that provides voltage control methods to quantum dot components

Together, these enable you to:
- Define voltage points with specific gate voltages
- Create sequences of voltage operations
- Execute complex voltage manipulation patterns
- Reuse common voltage operation sequences

## Core Concepts

### Voltage Points

A **voltage point** is a named configuration of voltages for one or more gates. Points are registered with quantum dot components and stored in the gate set for quick access.

```python
# Define a voltage point
qd.add_point(
    point_name="loading",
    voltages={"virtual_dot_1": 0.5, "barrier_gate_1": 0.3},
    duration=100
)
```

### Sequence Macros

A **`SequenceMacro`** encapsulates a single voltage operation (ramp or step) to a voltage point. It stores the operation type, target point, and timing parameters.

```python
from quam_builder.architecture.quantum_dots.components.macros import SequenceMacro

# Create a macro for ramping to a point
macro = SequenceMacro(
    macro_type="ramp",
    point_name="loading",
    duration=100,
    ramp_duration=500
)

# Execute the macro on a quantum dot
with qua.program() as prog:
    macro(qd)  # Ramps to the 'loading' point
```

### Sequences

A **sequence** is a named collection of `SequenceMacro` objects that can be executed together in order. Sequences are stored in the component and can be reused multiple times.

```python
# Define a sequence with multiple operations
qd.add_sequence(
    name="initialization_sequence",
    macro_types=["ramp", "step", "ramp"],
    voltages=[
        {"virtual_dot_1": 0.5},  # First point
        {"virtual_dot_1": 0.3},  # Second point
        {"virtual_dot_1": 0.0},  # Third point
    ],
    durations=[100, 200, 100],
    ramp_durations=[500, None, 300]
)

# Execute the entire sequence
with qua.program() as prog:
    qd.run_sequence("initialization_sequence")
```

## VoltagePointMacroMixin

The `VoltagePointMacroMixin` provides voltage control methods to quantum dot components. It's used by:
- `BarrierGate`
- `QuantumDot`
- `QuantumDotPair`
- `LDQubit`
- `LDQubitPair`

### Direct Voltage Methods

These methods set voltages directly without using pre-defined points:

```python
# Step to a voltage immediately
qd.step_to_voltages(voltage=0.5, duration=100)

# Ramp to a voltage over time
qd.ramp_to_voltages(voltage=0.5, ramp_duration=500, duration=100)

# Context-dependent voltage setting (for use in simultaneous blocks)
qd.go_to_voltages(voltage=0.5, duration=100)
```

### Point-Based Methods

These methods use pre-defined voltage points:

```python
# 1. Add a point
qd.add_point(
    point_name="idle",
    voltages={"virtual_dot_1": 0.2},
    duration=16
)

# 2. Step to the point
qd.step_to_point("idle", duration=100)

# 3. Ramp to the point
qd.ramp_to_point("idle", ramp_duration=500, duration=100)
```

### Sequence Methods

These methods create and execute sequences of voltage operations:

```python
# Method 1: Add individual points to a sequence
qd.add_point_to_sequence(
    sequence_name="my_sequence",
    point_name="point1",
    macro_type="ramp",
    duration=100,
    ramp_duration=500,
    voltages={"virtual_dot_1": 0.5}
)

qd.add_point_to_sequence(
    sequence_name="my_sequence",
    point_name="point2",
    macro_type="step",
    duration=200,
    voltages={"virtual_dot_1": 0.3}
)

# Method 2: Add a complete sequence at once
qd.add_sequence(
    name="complete_sequence",
    macro_types=["ramp", "step", "ramp"],
    voltages=[{...}, {...}, {...}],
    durations=[100, 200, 100],
    ramp_durations=[500, None, 300]
)

# Execute the sequence
with qua.program() as prog:
    qd.run_sequence("my_sequence")
```

## Usage Examples

### Example 1: Simple Voltage Control

```python
from qua import program, align

# Create quantum dot instance (assuming machine is already configured)
qd = machine.quantum_dots["virtual_dot_1"]

with program() as prog:
    # Step to a voltage
    qd.step_to_voltages(0.5, duration=100)

    # Ramp to another voltage
    qd.ramp_to_voltages(0.3, ramp_duration=500, duration=100)

    # Step back to zero
    qd.step_to_voltages(0.0, duration=100)
```

### Example 2: Using Voltage Points

```python
# Define voltage points for common configurations
qd.add_point("empty", voltages={"virtual_dot_1": 0.8}, duration=16)
qd.add_point("loading", voltages={"virtual_dot_1": 0.5}, duration=16)
qd.add_point("measurement", voltages={"virtual_dot_1": 0.2}, duration=16)

with program() as prog:
    # Ramp to loading position
    qd.ramp_to_point("loading", ramp_duration=500, duration=100)

    # Step to measurement position
    qd.step_to_point("measurement", duration=200)

    # Return to empty state
    qd.ramp_to_point("empty", ramp_duration=500, duration=100)
```

### Example 3: Creating and Running Sequences

```python
# Define a complete initialization sequence
qd.add_sequence(
    name="initialize",
    macro_types=["step", "ramp", "ramp"],
    voltages=[
        {"virtual_dot_1": 0.0},   # Reset
        {"virtual_dot_1": 0.5},   # Move to loading
        {"virtual_dot_1": 0.2},   # Move to measurement
    ],
    durations=[50, 100, 100],
    ramp_durations=[None, 500, 300]
)

# Define a readout sequence
qd.add_sequence(
    name="readout",
    macro_types=["step", "step"],
    voltages=[
        {"virtual_dot_1": 0.15},  # Pre-readout
        {"virtual_dot_1": 0.25},  # Readout
    ],
    durations=[100, 200],
)

with program() as prog:
    # Run initialization
    qd.run_sequence("initialize")

    # Perform measurement operations...
    # (other QUA code here)

    # Run readout
    qd.run_sequence("readout")
```

### Example 4: Multi-Component Simultaneous Operations

```python
qd1 = machine.quantum_dots["virtual_dot_1"]
qd2 = machine.quantum_dots["virtual_dot_2"]
barrier = machine.barrier_gates["barrier_1"]

# Add points to each component
qd1.add_point("target", voltages={"virtual_dot_1": 0.5})
qd2.add_point("target", voltages={"virtual_dot_2": 0.3})
barrier.add_point("open", voltages={"barrier_1": 0.7})

with program() as prog:
    with seq.simultaneous([qd1, qd2, barrier]):
        # These operations happen simultaneously
        qd1.go_to_point("target", duration=100)
        qd2.go_to_point("target", duration=100)
        barrier.go_to_point("open", duration=100)
```

### Example 5: Using SequenceMacro Directly

```python
from quam_builder.architecture.quantum_dots.components.macros import SequenceMacro

# Create macros manually
macro1 = SequenceMacro(
    macro_type="ramp",
    point_name="loading",
    duration=100,
    ramp_duration=500
)

macro2 = SequenceMacro(
    macro_type="step",
    point_name="measurement",
    duration=200
)

# Add points first
qd.add_point("loading", voltages={"virtual_dot_1": 0.5})
qd.add_point("measurement", voltages={"virtual_dot_1": 0.2})

with program() as prog:
    # Execute macros
    macro1(qd)
    macro2(qd)

    # Can override parameters at runtime
    macro1(qd, duration=150, ramp_duration=600)
```

### Example 6: LDQubit with Name Mapping

```python
# LDQubit automatically maps qubit names to quantum dot IDs
qubit = machine.qubits["qubit_1"]

# Use qubit name in voltages - automatically mapped to quantum dot ID
qubit.add_point(
    "idle",
    voltages={"qubit_1": 0.3},  # Mapped to quantum_dot ID internally
    duration=16
)

qubit.add_sequence(
    name="tune_up",
    macro_types=["ramp", "step"],
    voltages=[
        {"qubit_1": 0.5},  # Automatically mapped
        {"qubit_1": 0.2},
    ],
    durations=[100, 200],
    ramp_durations=[500, None]
)

with program() as prog:
    qubit.run_sequence("tune_up")
```

## Advanced Features

### Runtime Parameter Overrides

`SequenceMacro` supports runtime parameter overrides:

```python
macro = SequenceMacro(macro_type="ramp", point_name="target", duration=100)

with program() as prog:
    macro(qd)  # Use stored parameters
    macro(qd, duration=200)  # Override duration
    macro(qd, macro_type="step")  # Override type
```

### Sequence Reusability

Sequences can be executed multiple times:

```python
qd.add_sequence(
    name="reset",
    macro_types=["ramp"],
    voltages=[{"virtual_dot_1": 0.0}],
    durations=[100],
    ramp_durations=[300]
)

with program() as prog:
    for i in range(10):
        # Perform experiment
        # ...

        # Reset between iterations
        qd.run_sequence("reset")
```

### Point Replacement

Update existing points:

```python
# Add initial point
qd.add_point("target", voltages={"virtual_dot_1": 0.5})

# Replace it later (e.g., after calibration)
qd.add_point(
    "target",
    voltages={"virtual_dot_1": 0.52},  # Updated value
    replace_existing_point=True
)
```

## Macro Types

The system supports two macro types:

| Type | Description | Parameters |
|------|-------------|------------|
| `"ramp"` | Gradually change voltage over time | `ramp_duration`, `duration` |
| `"step"` | Instantly change voltage | `duration` |

- **ramp_duration**: Time taken to ramp from current to target voltage (ns)
- **duration**: Time to hold the final voltage (ns)

## Error Handling

The system provides clear error messages:

```python
# Invalid macro type
SequenceMacro(macro_type="invalid_type", ...)
# Raises: NotImplementedError: Type invalid_type not implemented. Supported types: ['ramp', 'step']

# Point not found
qd.step_to_point("nonexistent_point")
# Raises: ValueError: Point nonexistent_point not in registered points...

# Duplicate point without replace flag
qd.add_point("existing", voltages={...})
qd.add_point("existing", voltages={...})  # Without replace_existing_point=True
# Raises: ValueError: Point name existing already exists...
```

## Best Practices

1. **Define Points Early**: Define voltage points at the beginning of your experiment setup
2. **Use Descriptive Names**: Name points and sequences clearly (e.g., "loading_position", "readout_config")
3. **Group Related Operations**: Use sequences for operations that are always performed together
4. **Leverage Reusability**: Define sequences once and reuse them throughout your experiment
5. **Test Timing**: Ensure ramp and hold durations are appropriate for your hardware
6. **Handle Errors**: Use try-except blocks when working with dynamic point names

## Component-Specific Behavior

### BarrierGate & QuantumDot
- Voltage dictionaries use gate/dot IDs directly
- Standard voltage control

### QuantumDotPair
- Can control the detuning axis
- Uses virtual gate set transformations

### LDQubit & LDQubitPair
- Automatically map qubit names to quantum dot IDs
- Enables more intuitive voltage specifications
- Uses `self.name` as point name prefix instead of `self.id`

## See Also

- **VoltageSequence**: The underlying voltage sequence controller
- **VirtualGateSet**: Handles gate transformations and virtual axes
- **BaseQuamQD**: The root quantum dot machine configuration

## API Reference

For detailed API documentation, see the docstrings in `macros.py`:
- `SequenceMacro` class
- `VoltagePointMacroMixin` class

Each method includes comprehensive documentation with parameters, return values, exceptions, and examples.