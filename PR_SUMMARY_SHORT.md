# Quantum Dots Macro System Enhancement

## Summary

Comprehensive enhancement to the quantum dots macro system with a modern fluent API, optional voltages support, and operations registry integration.

**Stats:** 16 files changed, ~2,100+ additions / ~230 deletions, 65 tests passing

---

## Key Features

### 1. Enhanced Macro System with Fluent API

**New Macro Classes:**
- `BasePointMacro` - Abstract base following QuAM patterns
- `StepPointMacro` - Instant voltage transitions
- `RampPointMacro` - Gradual voltage transitions
- `SequenceMacro` - Composable macro sequences

**Fluent API:**
```python
(quantum_dot
    .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
    .with_ramp_point("load", {"virtual_dot_1": 0.3}, hold_duration=200, ramp_duration=500)
    .with_sequence("initialization", ["idle", "load"]))

quantum_dot.idle()  # Execute directly
quantum_dot.initialization()  # Run full sequence
```

### 2. Optional Voltages Parameter

Macro methods now support **two distinct use cases**:

**1. Create new point with macro:**
```python
qd.with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
```

**2. Convert existing point to macro:**
```python
qd.add_point("readout", {"virtual_dot_1": 0.2})
qd.with_step_point("readout", hold_duration=300)  # No voltages needed!
```

**Updated methods:**
- `with_step_point()` - voltages now `Optional`, defaults to `None`
- `with_ramp_point()` - voltages now `Optional`, defaults to `None`
- `add_point_with_step_macro()` - voltages now `Optional`, defaults to `None`
- `add_point_with_ramp_macro()` - voltages now `Optional`, defaults to `None`

**Benefits:**
- Flexible workflow - separate point definition from macro creation
- Better code organization
- Clear error messages (lists available points when point doesn't exist)

### 3. Operations Registry

New `operations.py` with QuAM's OperationsRegistry:

```python
# Define type-safe, auto-dispatched operations
@operations_registry.register_operation
def idle(component: VoltagePointMacroMixin, **kwargs):
    """Move component to idle voltage point."""
    pass

# Use in QUA with autocomplete and type checking
with program() as prog:
    idle(quantum_dot, hold_duration=150)
    load(quantum_dot)
    readout(quantum_dot)
```

**Registered operations:**
- Voltage: `idle`, `load`, `readout`, `sweetspot`
- Pulse: `x180`, `y180`, `x90`, `y90`
- Mixed: `rabi`

### 4. Sequence Composition

Build complex workflows from primitive operations:

```python
# Define primitives
(qd
    .with_step_point("idle", {"virtual_dot_1": 0.05}, hold_duration=100)
    .with_ramp_point("initialize", {"virtual_dot_1": 0.15}, hold_duration=200, ramp_duration=500)
    .with_step_point("manipulate", {"virtual_dot_1": 0.25}, hold_duration=150)
    .with_step_point("readout", {"virtual_dot_1": 0.12}, hold_duration=1000))

# Compose into sequences
qd.with_sequence("init", ["idle", "initialize"])
qd.with_sequence("measure", ["manipulate", "readout"])

# Create higher-level sequences
qd.with_sequence("full_experiment", ["init", "measure"])

# Execute
qd.full_experiment()
```

### 5. Default Parameter Values

All methods now have sensible defaults:
- `hold_duration=100` (ns)
- `ramp_duration=16` (ns)
- `point_duration=16` (ns)

More ergonomic API while still allowing customization.

---

## Testing

**New test files:**
- `test_macro_fluent_api.py` - 31 tests
  - Fluent API chaining
  - Optional voltages (both use cases)
  - Sequence composition
  - Parameter overrides
  - Error handling

- `test_macro_classes.py` - 34 tests
  - Macro class behavior
  - Reference system
  - Serialization
  - Nested sequences
  - Integration workflows

**Updated:**
- `test_voltage_point_macro_methods.py` - Extended (+500 lines)
- `conftest.py` - Fixed fixture parameter names

**Results:** 65/65 tests passing (100%)

---

## Documentation & Examples

**Enhanced docstrings:**
- Comprehensive descriptions
- Full type hints
- Parameter documentation
- Usage examples
- References to QuAM patterns

**Example Files:**

**`quam_qd_generator_example.py`** - Complete working examples
- Demonstrates full fluent API workflow
- Shows optional voltages usage (both creating new points and converting existing)
- Sequence composition patterns
- Real-world experiment setup

**`macro_examples.py`** - Comprehensive macro demonstrations
- Relocated to same level as `quam_qd_example.py` for better discoverability
- Updated imports: `.macros` → `.components.macros`
- Step-by-step examples of all macro types
- Best practices and usage patterns
- Covers StepPointMacro, RampPointMacro, and SequenceMacro

**See these files for practical usage examples and patterns!**

---

## Migration Guide

**Fluent API chaining:**
```python
(qd
    .with_step_point("idle", {"virtual_dot_1": 0.1}, hold_duration=100)
    .with_ramp_point("load", {"virtual_dot_1": 0.3}, hold_duration=200, ramp_duration=500)
    .with_sequence("cycle", ["idle", "load"]))
```

**Separate definition from macro:**
```python
# Define all points first
qd.add_point("idle", {"virtual_dot_1": 0.1})
qd.add_point("load", {"virtual_dot_1": 0.3})
qd.add_point("readout", {"virtual_dot_1": 0.15})

# Add macros for existing points
qd.with_step_point("idle", hold_duration=100)
qd.with_step_point("load", hold_duration=200)
qd.with_ramp_point("readout", hold_duration=300, ramp_duration=500)
```

**Operations registry:**

```python
from quam_builder.architecture.quantum_dots.examples.operations import operations_registry

machine.operations_registry = operations_registry

with program() as prog:
    idle(quantum_dot)
    load(quantum_dot, hold_duration=200)
```

---

## Files Changed

**Core macro system:**
- `components/macros.py` - Major enhancement (+1,000+ lines)
- `operations.py` - NEW file (+186 lines)

**Components:**
- `__init__.py` - Export new classes
- `components/operations.py` - NEW
- `components/quantum_dot.py` - Integration updates
- `components/quantum_dot_pair.py` - Enhanced operations
- `components/barrier_gate.py` - Minor updates
- `components/reservoir.py` - Macro support
- `components/xy_drive.py` - Drive operations

**Qubits:**
- `qubit/ld_qubit.py` - Macro integration
- `qubit_pair/ld_qubit_pair.py` - Pair operations

**Other:**
- `qpu/base_quam_qd.py` - Registry integration
- `quam_qd_generator_example.py` - Updated examples
- `macro_examples.py` - Relocated and enhanced
- `tools/voltage_sequence/voltage_sequence.py` - Minor cleanup

**Tests:**
- `test_macro_fluent_api.py` - NEW (31 tests)
- `test_macro_classes.py` - NEW (34 tests)
- `test_voltage_point_macro_methods.py` - Extended
- `conftest.py` - Fixed fixtures

---

## Key Improvements

 **Developer Experience**
- Fluent API for elegant code
- Flexible workflows
- Type safety with IDE autocomplete
- Clear error messages

️ **Architecture**
- Follows QuAM conventions
- Reference-based design
- Clean class hierarchy
- Proper serialization
