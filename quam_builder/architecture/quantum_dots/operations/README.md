> This document is the detailed guide for Quantum Dot Operations and Macros. For an overview of all quantum-dot QuAM components, operations, and macros, see [../README.md](../README.md).
# Quantum Dots Operations and Macro Defaults

This folder contains the default operations and catalog-based macro wiring system for quantum-dot QuAM components.
The main goal is to keep macro behavior decoupled from component classes while making defaults and user overrides explicit, composable, and serializable.

## Architecture Overview

Core modules:

- [`names.py`](./names.py): canonical string names (voltage points and macro names) as `StrEnum`s.
- [`default_macros/`](./default_macros): built-in macro classes and default per-component macro maps.
- [`macro_catalog.py`](./macro_catalog.py): `MacroCatalog` protocol, `MacroRegistry`, and built-in catalogs (`UtilityMacroCatalog`, `DefaultMacroCatalog`, `VoltageBalancedMacroCatalog`, `TypeOverrideCatalog`).
- [`pulse_catalog.py`](./pulse_catalog.py): helper builders for the default pulse materialization pass (`LDQubit` XY pulses, `SensorDot` readout).
- [`../macro_engine/wiring.py`](../macro_engine/wiring.py): runtime wiring API (`wire_machine_macros`) that materializes macro and pulse defaults and applies overrides.
- [`default_operations.py`](./default_operations.py): operation signatures exposed through `OperationsRegistry`.

## Macro System Design

```
                       ┌────────────────────┐
                       │    wire_machine_macros()   │   User-facing entry point
                       └─────────┬──────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     MacroRegistry       │   Aggregates catalogs
                    │  (sorted by priority)   │
                    └────────────┬────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌────────▼─────────┐  ┌─────────▼──────────┐  ┌─────────▼──────────┐
│UtilityMacroCatalog│ │DefaultMacroCatalog │  │ User Catalog(s)    │
│   priority = 0    │ │  priority = 100    │  │ priority = 200+    │
│ align, wait       │ │ MRO-based defaults │  │ Lab-owned macros   │
└───────────────────┘ └────────────────────┘  └────────────────────┘
```

Resolution order: catalogs are merged low-to-high priority. Higher priority wins per macro name. Instance overrides are applied last.

## Canonical Names

Canonical names are centralized in [`names.py`](./names.py) as `StrEnum`s:

- `VoltagePointName`: `initialize`, `measure`, `empty`, `exchange`, `CZ`
- `SingleQubitMacroName`: state macros + gate macros (`xy_drive`, `x`, `y`, `z`, `x180`, `x90`, ...)
- `TwoQubitMacroName`: state macros + gate macros (`cnot`, `cz`, `crot`, `swap`, `iswap`)
- `DrivePulseName`: `gaussian`, `square`, `kaiser`, `hermite`, `drag`

Since these are `StrEnum`s, `SingleQubitMacroName.X_180` already behaves like `"x180"`.

## Default Macro Logic by Component Type

### Utility macros (all macro-dispatch components)

From [`../../../tools/macros/default_macros.py`](../../../tools/macros/default_macros.py):

- `align`
- `wait`

### `QPU`

- `initialize`, `measure`, `empty`

### `LDQubit`

- State macros: `initialize`, `measure`, `empty`, `exchange`
- Canonical 1Q macros: `xy_drive`, `x`, `y`, `z`
- Fixed-angle wrappers: `x180`, `x90`, `x_neg90`, `y180`, `y90`, `y_neg90`, `z180`, `z90`
- Identity: `I`

Canonical chain: `x`/`y` delegate to `xy_drive` with phase offsets; fixed-angle wrappers delegate to canonical axes.

### `LDQubitPair`

- State macros: `initialize`, `measure`, `empty`, `exchange`
- Two-qubit gates: `cz` (`CZMacro`, exchange-style), `crot` (`CROTMacro`); `cnot`, `swap`, `iswap` are placeholders until user-supplied

## Wire Machine API

The top-level API is `wire_machine_macros()`:

```python
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros

wire_machine_macros(machine)
```

### With a lab catalog

```python
from my_lab_macros.catalog import LabMacroCatalog

wire_machine_macros(machine, catalogs=[LabMacroCatalog()])
```

### With instance overrides

```python
from quam_builder.architecture.quantum_dots.operations.names import SingleQubitMacroName

wire_machine_macros(
    machine,
    instance_overrides={
        "qubits.q1": {
            SingleQubitMacroName.X_180: TunedX180Macro,
        },
    },
)
```

### With type-level overrides (ad-hoc)

```python
from functools import partial
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from quam_builder.architecture.quantum_dots.operations.macro_catalog import TypeOverrideCatalog
from quam_builder.architecture.quantum_dots.operations.names import SingleQubitMacroName
from quam_builder.architecture.quantum_dots.qubit import LDQubit

wire_machine_macros(
    machine,
    catalogs=[
        TypeOverrideCatalog({
            LDQubit: {
                SingleQubitMacroName.INITIALIZE: partial(InitMacro, ramp_duration=64),
            },
        }),
    ],
)
```

### Disabling a macro

```python
from quam_builder.architecture.quantum_dots.macro_engine import DISABLED

wire_machine_macros(
    machine,
    instance_overrides={
        "qubit_pairs.q1_q2": {
            TwoQubitMacroName.CZ: DISABLED,
        },
    },
)
```

## Override Precedence

1. `UtilityMacroCatalog` (priority 0) -- `align`, `wait`
2. `DefaultMacroCatalog` (priority 100) -- architecture defaults
3. User catalogs (priority 200+) -- lab packages, `TypeOverrideCatalog`
4. Instance overrides -- per-component-path, applied last

Effective: `instance override` > `catalog (highest priority)` > `default`.

## MacroCatalog Protocol

Any object implementing `get_factories(component_type) -> MacroFactoryMap` and `priority -> int` can be registered as a catalog:

```python
from quam_builder.architecture.quantum_dots.operations.macro_catalog import MacroFactoryMap

class LabMacroCatalog:
    priority = 200

    def get_factories(self, component_type: type) -> MacroFactoryMap:
        from quam_builder.architecture.quantum_dots.qubit import LDQubit

        if issubclass(component_type, LDQubit):
            return {
                SingleQubitMacroName.INITIALIZE: LabInitMacro,
                SingleQubitMacroName.X: LabXMacro,
            }
        return {}
```

### MacroFactory types

A factory is either:

- A `QuamMacro` subclass (called with no args to instantiate)
- A zero-arg callable returning a `QuamMacro` (e.g. `functools.partial(InitMacro, ramp_duration=64)`)

## Targeting Component Instances

Instance override keys are component paths:

- `qpu`
- `qubits.q1`
- `qubit_pairs.q1_q2`
- `quantum_dots.dot_1`
- `quantum_dot_pairs.dot_1_dot_2`
- `sensor_dots.s1`
- `barrier_gates.b12`
- `global_gates.g1`

Only components with a `macros` mapping are eligible.

## Error Handling

Invalid instance override paths (e.g. a typo like `"qubits.q99"`) and
`DISABLED` removals targeting non-existent macros always raise `KeyError`.
This catches configuration mistakes early.

## Single-Qubit Gate Composition Model

### Delegation chain

```
q.x90()                      # fixed-angle wrapper
  -> q.macros["x"].apply()   # canonical axis macro (adds phase=0 for X)
       -> q.macros["xy_drive"].apply()  # core XY drive
            -> q.virtual_z(phase)
            -> q.voltage_sequence.step_to_voltages(...)
            -> q.xy.play(pulse_name, amplitude_scale, duration)
            -> q.virtual_z(-phase)
```

Overriding one canonical macro automatically affects all wrappers above it.

### Source of truth

The reference pulse is the single source of truth for all single-qubit XY rotations:

```python
qubit.xy.operations[qubit.macros["xy_drive"].reference_pulse_name]
```

### What to calibrate

| Parameter | Where it lives | Affects |
|-----------|---------------|---------|
| Pi-pulse amplitude | `qubit.xy.operations["gaussian_x180"].amplitude` | All XY gates |
| Pulse envelope (family) | `machine.pulse_family` / `set_pulse_family()` | All XY gates |
| Pulse length / shape | `qubit.xy.operations["gaussian_x90"]` (`length`, `sigma_ratio`, …) | All XY gates in that family |
| Drive frequency | `qubit.xy.intermediate_frequency` | All XY gates |
| Reference angle | `qubit.macros["xy_drive"].reference_angle` | Scale factor (default: pi) |
| Voltage points | `qubit.add_point("initialize", {...})` | State macros |

## Default Pulse Wiring

`wire_machine_macros()` also wires default pulses onto component channels via `PulseWirer`. Pulse wiring is additive -- only pulse names not already present are added.

### XY Drive Pulse

Five pulse families (Gaussian, Square, Kaiser, Hermite, DRAG) are loaded per qubit with the naming convention `{family}_{gate}` (e.g. `"gaussian_x90"`, `"drag_x180"`). Default length 1000 ns, amplitude 1.0. Drive-type aware: `SingleChannel` gets `axis_angle=None`; IQ/MW gets `axis_angle=0.0`. The active family is selected via `machine.pulse_family`.

### Readout Pulse

`SquareReadoutPulse` named `"readout"` on each sensor dot resonator (length 2000 ns, amplitude 1.0).

## Readout macros

State and readout behaviour for dots and pairs is implemented in [`default_macros/state_macros.py`](default_macros/state_macros.py).

| Macro | Component | Role |
|-------|-----------|------|
| **`SensorDotMeasureMacro`** | `SensorDot` | Plays readout pulse; with `quantum_dot_pair_id`, applies stored projector/threshold and returns a QUA boolean. |
| **`MeasurePSBPairMacro`** | `QuantumDotPair`, `LDQubitPair` | Steps to `"measure"` voltage point (optional `buffer_duration`), aligns gates with resonator, delegates to sensor macro. |
| **`QPUMeasureMacro`** | `QPU` | Broadcasts measure to active qubits/pairs/dots. |
| **`InitializeStateMacro`**, **`EmptyStateMacro`**, **`ExchangeStateMacro`** | Many types | Voltage-point state transitions (ramp/step). |

### Calibrating readout macros

| Parameter | Macro | Notes |
|-----------|-------|-------|
| Measure voltage point | `MeasurePSBPairMacro.point` | Named point or explicit voltage dict |
| Pre-readout buffer | `MeasurePSBPairMacro.buffer_duration` | Hold at measure point before RF pulse (ns) |
| Threshold / projector | `SensorDot.readout_thresholds`, `readout_projectors` | Per pair; assign the dict fields directly |
| Pulse name | `SensorDotMeasureMacro.pulse_name` | Default `"readout"`; pair-specific `"readout_{pair_id}"` if registered |

`MeasurePSBPairMacro.inferred_duration` returns **seconds**: `(buffer_duration_ns * 1e-9) + sensor_macro.inferred_duration`. The public contract for custom macros is also seconds (see [voltage_sequence/README.md — Custom Macro Duration Contract](../voltage_sequence/README.md#custom-macro-duration-contract)).

Setup guide: [components/README.md](../components/README.md).

## Voltage-balanced macros

For **AC-coupled** gate lines, default state macros can leave a non-zero net integrated voltage. Register **`VoltageBalancedMacroCatalog`** (priority 200) to replace state macros with zero-integral variants:

```python
from quam_builder.architecture.quantum_dots.operations.macro_catalog import VoltageBalancedMacroCatalog
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros

wire_machine_macros(machine, catalogs=[VoltageBalancedMacroCatalog()])
```

**Conventions** (see [`voltage_balanced_macros/state_macros.py`](voltage_balanced_macros/state_macros.py)):

- **`initialize`** point is 0 V on every channel (rest state, not travelled to).
- **`empty`** and **`measure`** points store **positive-polarity** targets; negative segments are derived at runtime.
- Macros start and end at 0 V with zero net ∫V·dt per channel.

Notable classes: `BalancedInitializeMacro`, `BalancedEmptyMacro`, `BalancedMeasurePSBPairMacro`, `BalancedDCz2QMacro`, `TwoStageBalancedInitializeMacro`.

Examples: [`voltage_balanced_macros_example.py`](../examples/voltage_balanced_macros_example.py), [`dcz_macro_example.py`](../examples/dcz_macro_example.py), [`qm_example.py`](../examples/qm_example.py).

## Two-qubit macros

Default registrations on **`LDQubitPair`**:

| Name | Default class | Status |
|------|---------------|--------|
| `cz` | `CZMacro` | Exchange-style CZ; requires calibrated `"exchange"` / detuning points |
| `crot` | `CROTMacro` | Controlled rotation via virtual-Z on both qubits |
| `cnot`, `swap`, `iswap` | Placeholder macros | Raise at runtime until you supply lab overrides |

Override with `TypeOverrideCatalog`, instance overrides, or an external catalog. Detuning-based **`BalancedDCz2QMacro`** (balanced catalog) is demonstrated in [`dcz_macro_example.py`](../examples/dcz_macro_example.py).

## OperationsRegistry

[`default_operations.py`](default_operations.py) exposes a typed **`operations_registry`** for protocol-style code that dispatches by operation name:

```python
from quam_builder.architecture.quantum_dots.operations.default_operations import operations_registry

operations_registry.x180(q1)
operations_registry.measure(pair)
```

Each registered function is a stub; runtime dispatch goes to `component.macros[name]`. Prefer **`q.x180()`** when the component type is known; use the registry when writing generic algorithms over `QuantumComponent` / `Qubit` / `QubitPair`.

## External Macro Package Pattern

Keep lab-owned macro logic in a separate package:

```python
# my_lab_macros/catalog.py
from quam_builder.architecture.quantum_dots.operations.macro_catalog import MacroFactoryMap
from quam_builder.architecture.quantum_dots.operations.names import SingleQubitMacroName

class LabMacroCatalog:
    priority = 200

    def get_factories(self, component_type: type) -> MacroFactoryMap:
        from quam_builder.architecture.quantum_dots.qubit import LDQubit
        if issubclass(component_type, LDQubit):
            return {
                SingleQubitMacroName.INITIALIZE: LabInitMacro,
                SingleQubitMacroName.X: LabXMacro,
            }
        return {}
```

At the experiment call site:

```python
from my_lab_macros.catalog import LabMacroCatalog
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros

wire_machine_macros(machine, catalogs=[LabMacroCatalog()])
```

This keeps custom defaults out of `quam-builder` itself.

## Builder Integration

`build_base_quam()`, `build_loss_divincenzo_quam()`, and `build_quam()` all accept `catalogs` and `instance_overrides`.

## Examples

- [`../examples/macro_defaults_example.py`](../examples/macro_defaults_example.py): default-only wiring and parameterization.
- [`../examples/macro_overrides_example.py`](../examples/macro_overrides_example.py): catalog and instance overrides.
- [`../examples/pulse_overrides_example.py`](../examples/pulse_overrides_example.py): pulse wiring and configuration.
- [`../examples/full_workflow_example.py`](../examples/full_workflow_example.py): complete end-to-end workflow.
- [`../examples/external_macro_package_example.py`](../examples/external_macro_package_example.py): external catalog package pattern.
- [`../examples/voltage_balanced_macros_example.py`](../examples/voltage_balanced_macros_example.py): balanced state macros + cloud simulation.
- [`../examples/dcz_macro_example.py`](../examples/dcz_macro_example.py): detuning-based CZ with balanced catalog.
