# Quantum Dots Operations and Macro Defaults

This folder contains the default operations + macro wiring system for quantum-dot QuAM components.
The main goal is to keep macro behavior decoupled from component classes while making defaults and user overrides explicit, composable, and serializable.

## Architecture Overview

Core modules:

- [`names.py`](./names.py): canonical string names (voltage points and macro names).
- [`default_macros/`](./default_macros): built-in macro classes and default per-component macro maps.
- [`macro_registry.py`](./macro_registry.py): component-type -> default macro factory registration/resolution.
- [`component_macro_catalog.py`](./component_macro_catalog.py): idempotent registration of architecture defaults (`QPU`, `LDQubit`, `LDQubitPair`).
- [`pulse_registry.py`](./pulse_registry.py): component-type -> default pulse factory registration/resolution (parallel to macro registry).
- [`component_pulse_catalog.py`](./component_pulse_catalog.py): idempotent registration of default pulse factories (`LDQubit` XY pulses, `SensorDot` readout).
- [`../macro_engine/wiring.py`](../macro_engine/wiring.py): runtime wiring API (`wire_machine_macros`) that materializes macro and pulse defaults and applies overrides.
- [`default_operations.py`](./default_operations.py): operation signatures exposed through `OperationsRegistry`.

## Canonical Voltage Point Enums

Voltage-point names are centralized in [`names.py`](./names.py):

- `initialize`
- `measure`
- `empty`
- `exchange`

These are represented by `VoltagePointName` (`StrEnum`) and reused by default state macros.
Default state macros assume these points exist in each relevant voltage sequence (for example via `add_point(...)`).
In Python examples below, prefer the enum members directly.
These are `StrEnum`s, so `TwoQubitMacroName.CZ` already behaves like `"cz"`.
In TOML profiles, use the serialized enum values (`initialize`, `x180`, `gaussian`, ...).

Canonical macro names are also centralized as enums in the same module:

- `SingleQubitMacroName` for built-in 1Q defaults — state macros (`initialize`, `measure`, `empty`, `exchange`) and gate macros (`xy_drive`, `x`, `y`, `z`, `x180`, ...)
- `TwoQubitMacroName` for built-in 2Q defaults — state macros (`initialize`, `measure`, `empty`, `exchange`) and gate macros (`cnot`, `cz`, `swap`, `iswap`)

Alias spellings (for example `-x90`, `-y90`) remain explicit strings via
`SINGLE_QUBIT_MACRO_ALIASES` and `SINGLE_QUBIT_MACRO_ALIAS_MAP`.

## Default Macro Logic by Component Type

### Utility macros (all macro-dispatch components)

From [`../../../tools/macros/default_macros.py`](../../../tools/macros/default_macros.py):

- `align`
- `wait`

### `QPU`

From [`default_macros/state_macros.py`](./default_macros/state_macros.py):

- `initialize`
- `measure`
- `empty`

QPU state macros dispatch to active qubits/pairs when configured; otherwise they broadcast to all registered qubits/pairs (with stage-1 fallbacks).

### `LDQubit`

From [`default_macros/single_qubit_macros.py`](./default_macros/single_qubit_macros.py):

- State macros: `initialize`, `measure`, `empty`, `exchange`
- Canonical 1Q macros: `xy_drive`, `x`, `y`, `z`
- Fixed-angle wrappers: `x180`, `x90`, `x_neg90` (and `-x90` alias), `y180`, `y90`, `y_neg90` (and `-y90` alias), `z180`, `z90`
- Identity: `I`

Canonical chain:

- `x` and `y` delegate to `xy_drive` with phase offsets.
- `x90`/`x180`/`x_neg90` and `y*` wrappers delegate to canonical `x`/`y`.
- `z90`/`z180` wrappers delegate to canonical `z`.
- Negative XY angles are encoded as positive-angle drives with an additional `+pi`
  phase shift (on top of the axis phase), so amplitude scaling is based on
  `abs(angle)`.

Practical consequence: overriding one canonical macro (for example `xy_drive` or `x`) automatically affects all wrappers above it.

### `LDQubitPair`

From [`default_macros/two_qubit_macros.py`](./default_macros/two_qubit_macros.py):

- State macros: `initialize`, `measure`, `empty`, `exchange`
- Two-qubit gates: `cnot`, `cz`, `swap`, `iswap`

The `exchange` macro ramps to a configurable exchange voltage point, holds for a wait duration, then ramps back to the initialize point. Ramp duration, wait duration, and both voltage targets are configurable via class fields and runtime kwargs.

Default two-qubit gate macros (`cnot`, `cz`, `swap`, `iswap`) are explicit placeholders (`NotImplementedError`) until user calibration logic is supplied through overrides.

## Invocation Paths: Registry vs Direct vs Macro

All invocation paths ultimately execute `macro.apply()`. Choose based on your use case:

| Invocation | When to use | Applicable component types |
|------------|-------------|----------------------------|
| `from ...default_operations import x180; x180(q)` | Generic algorithms, type-safe protocol code, IDE completion | LDQubit (1Q gates); LDQubitPair (2Q gates); QuantumDot, QuantumDotPair, SensorDot (state macros) |
| `q.x180()` | Component-specific code; natural direct call via `__getattr__` dispatch | Same as registry |
| `q.macros["x180"].apply()` | Direct access; use when you need the macro object itself (introspection, custom dispatch) | Any component with `macros` dict |

`q.x180()` and `q.macros["x180"].apply()` are equivalent — `__getattr__` returns `macro.apply` directly.

See [`default_operations.py`](./default_operations.py) module docstring for the registry vs direct comparison in prose.

## When and Where Macros Are Wired

Wiring happens in three places:

1. Component construction (`MacroDispatchMixin.__post_init__`): materializes missing defaults.
2. Build flow (`build_base_quam`, `build_loss_divincenzo_quam`, `build_quam`): calls `wire_machine_macros(...)`.
3. Load flow (`BaseQuamQD.load`, `LossDiVincenzoQuam.load`): calls `wire_machine_macros(instance)` after load.

Important behavior:

- Default materialization is additive: only missing default macro names are inserted.
- Existing macro entries are not reset unless an override explicitly targets that name.

## Override Model (Detailed)

`wire_machine_macros` supports two override scopes via typed kwargs:

- `component_overrides={LDQubit: overrides(macros={...})}` — all instances of a type
- `instance_overrides={"qubits.q1": overrides(macros={...})}` — one specific instance

Use the helpers from `quam_builder.architecture.quantum_dots.macro_engine`:

| Helper | Purpose |
|--------|---------|
| `macro(Factory, **params)` | Create a macro override entry (validates factory is QuamMacro) |
| `pulse("GaussianPulse", **params)` | Create a pulse override entry |
| `disabled()` | Remove a macro or pulse |
| `overrides(macros={...}, pulses={...})` | Group macro and pulse overrides for one component |

### Precedence and Merge Order

1. Architecture defaults (registry/catalog).
2. TOML profile from `macro_profile_path`.
3. `component_overrides` applied to each matching instance.
4. `instance_overrides` applied last.

So, effective precedence for a specific macro name on one component is:

`instance override` > `type override` > `TOML profile` > `default`.

### Targeting Component Types

Type override keys use the actual Python class (recommended) or a string:

- class reference: `LDQubit` (import-time validation, IDE autocomplete)
- short class name string: `"LDQubit"` (for TOML profiles)
- fully qualified string: `"quam_builder.architecture.quantum_dots.qubit.LDQubit"`

### Targeting Component Instances

Instance override keys are component paths, for example:

- `qpu`
- `qubits.q1`
- `qubit_pairs.q1_q2`
- `quantum_dots.dot_1`
- `quantum_dot_pairs.dot_1_dot_2`
- `sensor_dots.s1`
- `barrier_gates.b12`
- `global_gates.g1`

Only components exposing a `macros` mapping are eligible.

### Macro Entry Forms (Python)

Use the `macro()` helper to build entries:

```python
from quam_builder.architecture.quantum_dots.macro_engine import macro, disabled

# With parameters:
macro(InitializeStateMacro, ramp_duration=64)

# Class only (no extra params):
macro(TunedX180Macro)

# Import-path string (for TOML compatibility):
macro("my_pkg.macros:TunedX180Macro")
```

`macro()` validates at call time that the factory is a `QuamMacro` subclass.

### Macro Entry Forms (TOML)

TOML profiles use string keys and the `factory` / `params` / `enabled` format:

```toml
[component_types.LDQubit.macros.initialize]
factory = "my_pkg.macros:CustomInitializeMacro"
enabled = true
[component_types.LDQubit.macros.initialize.params]
ramp_duration = 64

[component_types.LDQubitPair.macros]
cz = "my_pkg.macros:CalibratedCZMacro"
```

### Disable/Remove a Macro

Python:

```python
instance_overrides={
    "qubit_pairs.q1_q2": overrides(macros={
        TwoQubitMacroName.CZ: disabled(),
    }),
}
```

TOML:

```toml
[instances."qubit_pairs.q1_q2".macros.cz]
enabled = false
```

### Strict vs Non-Strict Mode

- `strict=True` (default):
  - unknown component path -> error
  - unknown macro name for that component -> error
- `strict=False`:
  - unknown paths are ignored
  - unknown macro names can be added (or ignored on removal)

Use `strict=True` in production profiles to catch typos early.

## How Users Override Only One Macro and Keep Defaults

This is the common case and is fully supported.

Example: override only `x180` on one qubit; all other macros remain default.

```python
from quam_builder.architecture.quantum_dots.macro_engine import (
    wire_machine_macros, macro, overrides,
)
from quam_builder.architecture.quantum_dots.operations.names import SingleQubitMacroName

wire_machine_macros(
    machine,
    instance_overrides={
        "qubits.q1": overrides(macros={
            SingleQubitMacroName.X_180: macro(TunedX180Macro),
        }),
    },
    strict=True,
)
```

Result:

- `qubits.q1.macros["x180"]` is replaced with `TunedX180Macro`.
- All other macros on `q1` are untouched.
- All macros on other qubits are untouched.
- Persistent single-qubit amplitude calibration should live on the reference
  pulse object, not on wrapper macros.

## Type-Level Override + Instance-Level Specialization

Pattern: set lab-wide default for a component type, then specialize one device instance.

```python
from quam_builder.architecture.quantum_dots.macro_engine import (
    wire_machine_macros, macro, overrides,
)
from quam_builder.architecture.quantum_dots.operations.names import SingleQubitMacroName
from quam_builder.architecture.quantum_dots.qubit import LDQubit

wire_machine_macros(
    machine,
    component_overrides={
        LDQubit: overrides(macros={
            SingleQubitMacroName.INITIALIZE: macro(InitMacro, ramp_duration=64),
        }),
    },
    instance_overrides={
        "qubits.q2": overrides(macros={
            SingleQubitMacroName.INITIALIZE: macro(InitMacro, ramp_duration=96),
        }),
    },
)
```

`qubits.q2` wins over type-level settings because instance overrides are applied last.

## Profile + Runtime Combination

Typical workflow:

1. Keep stable, shared calibration defaults in TOML (`macro_profile_path`).
2. Apply session-specific tweaks with `component_overrides` / `instance_overrides` in Python.

Because runtime overrides are deep-merged over profile data, users can patch only one leaf value without duplicating the full profile map.

## Importing a Full Macro Catalog From Another Package

For users who want a custom default set that survives upstream pulls, keep macro logic in a separate package/repo and import it as `component_overrides`.

### Where This Should Sit

Use this layout:

1. External package (stable lab-owned code): `my_lab_qd_macros/`
2. Experiment/build entrypoint (in your experiment repo): where `wire_machine_macros(...)` is called
3. Optional local TOML for small per-run tweaks

### External package example

`my_lab_qd_macros/catalog.py`:

```python
from __future__ import annotations

from quam_builder.architecture.quantum_dots.macro_engine import macro, pulse, overrides
from quam_builder.architecture.quantum_dots.operations.names import (
    DrivePulseName,
    SingleQubitMacroName,
    TwoQubitMacroName,
    VoltagePointName,
)
from quam_builder.architecture.quantum_dots.components import QPU
from quam_builder.architecture.quantum_dots.qubit import LDQubit
from quam_builder.architecture.quantum_dots.qubit.ld_qubit_pair import LDQubitPair

from .single_qubit import LabInitialize1Q, LabMeasure1Q, LabEmpty1Q, LabX, LabY, LabZ
from .two_qubit import LabCZ, LabISWAP, LabCNOT, LabSWAP
from .qpu import LabInitializeQPU, LabMeasureQPU, LabEmptyQPU


def build_component_overrides() -> dict:
    """Return component_overrides dict for wire_machine_macros."""
    return {
        QPU: overrides(macros={
            VoltagePointName.INITIALIZE: macro(LabInitializeQPU),
            VoltagePointName.MEASURE: macro(LabMeasureQPU),
            VoltagePointName.EMPTY: macro(LabEmptyQPU),
        }),
        LDQubit: overrides(
            macros={
                SingleQubitMacroName.INITIALIZE: macro(LabInitialize1Q),
                SingleQubitMacroName.MEASURE: macro(LabMeasure1Q),
                SingleQubitMacroName.EMPTY: macro(LabEmpty1Q),
                SingleQubitMacroName.X: macro(LabX),
                SingleQubitMacroName.Y: macro(LabY),
                SingleQubitMacroName.Z: macro(LabZ),
            },
            pulses={
                DrivePulseName.GAUSSIAN: pulse(
                    "GaussianPulse", length=1000, amplitude=0.17, sigma=167,
                ),
            },
        ),
        LDQubitPair: overrides(macros={
            TwoQubitMacroName.CNOT: macro(LabCNOT),
            TwoQubitMacroName.CZ: macro(LabCZ),
            TwoQubitMacroName.SWAP: macro(LabSWAP),
            TwoQubitMacroName.ISWAP: macro(LabISWAP),
        }),
    }
```

### Experiment call site example

In your experiment repo, at the machine-build call site:

```python
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros
from my_lab_qd_macros.catalog import build_component_overrides

wire_machine_macros(
    machine,
    component_overrides=build_component_overrides(),
    strict=True,
)
```

This keeps custom defaults out of `quam-builder` itself, so pulling upstream changes does not overwrite your catalog.

### Optional pattern: catalog defaults + local one-off tweak

```python
from quam_builder.architecture.quantum_dots.macro_engine import (
    wire_machine_macros, macro, overrides,
)
from quam_builder.architecture.quantum_dots.operations.names import SingleQubitMacroName
from my_lab_qd_macros.catalog import build_component_overrides

wire_machine_macros(
    machine,
    component_overrides=build_component_overrides(),
    instance_overrides={
        "qubits.q3": overrides(macros={
            SingleQubitMacroName.X_180: macro(
                "my_lab_qd_macros.single_qubit:Q3TunedX180"
            ),
        }),
    },
    strict=True,
)
```

This is the recommended model for common lab usage: central catalog + selective per-device override.

## Calibrated Parameters: Storage and Persistence

There are two storage layers:

1. Source-of-truth config (optional):
   - TOML profile in your repository/lab config.
2. Runtime QuAM object:
   - instantiated macro objects in `component.macros`
   - pulse objects in channel `operations` mappings

Parameter examples:

- `machine.qubits["q1"].macros[SingleQubitMacroName.INITIALIZE].ramp_duration`
- `machine.qubits["q1"].xy.operations[DrivePulseName.GAUSSIAN].amplitude`

Serialization behavior:

- Macro objects/fields in `component.macros` are part of QuAM state.
- Pulse objects/fields in `channel.operations` are part of QuAM state.

## Recommended Override Strategy

1. Override the reference pulse first if you want broad single-qubit amplitude or envelope changes.
2. Use canonical macros (`xy_drive`, `x`, `y`, `z`) for behavior changes such as phase logic or dispatch behavior.
3. Avoid persistent amplitude defaults on wrapper macros; keep amplitude calibration on the pulse object itself.
4. Keep two-qubit calibrated logic in profile/type-level overrides and specialize only exceptional instances.
5. Use `strict=True` for CI and release configs.

## Default Pulse Wiring

`wire_machine_macros()` also wires default pulses onto component channels. Pulse wiring is additive — only pulse names not already present are added.

### Qubit XY Drive Pulse

A single reference pulse is registered per qubit. `XYDriveMacro` scales amplitude for rotation angle and applies virtual-Z for rotation axis (X/Y), so all single-qubit gates derive from this one pulse.

Composition rules:
- `x`/`y` add their canonical axis phase to any runtime `phase=...`.
- `xy_drive` runtime `amplitude_scale=...` multiplies the angle-derived scale from the reference pulse instead of replacing it.

### Single-Qubit Gate Composition Model

#### Delegation chain

All single-qubit XY gate calls flow through a strict delegation chain:

```
q.x90()                      # fixed-angle wrapper
  └─ q.macros["x"].apply()   # canonical axis macro (adds phase=0 for X)
       └─ q.macros["xy_drive"].apply()  # core XY drive
            ├─ q.virtual_z(phase)       # frame rotation (if phase != 0)
            ├─ q.voltage_sequence.step_to_voltages({}, duration)  # hold voltages
            ├─ q.xy.play(pulse_name, amplitude_scale, duration)   # hardware play
            └─ q.virtual_z(-phase)      # restore frame
```

Overriding a single canonical macro automatically affects all wrappers above it. For example, replacing `xy_drive` changes the behavior of every XY gate.

#### Source of truth

The reference pulse is the single source of truth for all single-qubit XY rotations:

```python
qubit.xy.operations[qubit.macros["xy_drive"].reference_pulse_name]
```

- Pulse-envelope parameters (`amplitude`, `length`, `sigma`, `axis_angle`, `alpha`, `anharmonicity`) live on that pulse object, not in the wrapper macros.
- Replacing the pulse object, or switching `reference_pulse_name`, updates the whole single-qubit gate family.
- All gates derive their amplitude scale from the reference pulse using: `abs(angle) / reference_angle`.

#### What to calibrate

| Parameter | Where it lives | Affects |
|-----------|---------------|---------|
| Pi-pulse amplitude | `qubit.xy.operations["gaussian"].amplitude` | All XY gates (single source of truth) |
| Pulse envelope shape | `qubit.xy.operations["gaussian"]` (length, sigma, etc.) | All XY gates |
| Drive frequency | `qubit.xy.intermediate_frequency` / `qubit.xy.LO_frequency` | All XY gates |
| Reference angle | `qubit.macros["xy_drive"].reference_angle` | Scale factor mapping (default: pi) |
| Voltage points | `qubit.add_point("initialize", {...})` etc. | State macros |

#### Modulation order

- `xy_drive` converts `angle` into an angle-derived amplitude scale: `abs(angle) / reference_angle`. Duration is always the reference pulse length (no stretching).
- `x` or `y` adds its axis phase (`0` for X, `pi/2` for Y) to any runtime `phase`.
- A fixed-angle wrapper such as `x90` contributes its default angle only.
- Runtime `amplitude_scale` multiplies the angle-derived scale (compositional, not replacing).
- Runtime `duration` / `pulse_duration` overrides the reference pulse duration.

#### Negative angle handling

Negative angles are encoded as positive-angle drives with a `+pi` phase shift on top of the axis phase. This means amplitude scaling is always computed from `abs(angle)`, and the sign information is carried in the virtual-Z frame rotation.

#### Effective play parameters

- Effective phase = `sign-normalization phase + axis phase + wrapper phase + runtime phase`
- Effective amplitude scale = `(abs(angle) / reference_angle) * runtime amplitude_scale`
- Effective duration = `runtime duration` if provided, otherwise reference pulse length

#### Representative cases

1. Base calibration only
   - Reference pulse: gaussian with `amplitude=1.0`, `length=1000`
   - Call: `q.x180()`
   - Result: plays with scale `1.0`, phase `0`, duration `1000 ns`

2. Calibrated amplitude
   - `q.xy.operations["gaussian"].amplitude = 0.17`
   - Call: `q.x180()` → effective amplitude `0.17 * 1.0`
   - Call: `q.x90()` → effective amplitude `0.17 * 0.5`
   - Consistency: both derive from the same pulse object

3. Runtime modulation
   - Call: `q.y90(amplitude_scale=0.5, phase=0.1)`
   - Effective phase: `pi/2 + 0.1`
   - Effective amplitude scale: `0.5 * 0.5 = 0.25` (runtime multiplies angle-derived)

4. Negative rotation
   - Call: `q.x(angle=-pi/2)`
   - Effective phase: `0 + pi` (sign-flip phase)
   - Effective amplitude scale: `0.5` (from `abs(-pi/2) / pi`)
   - Frame is restored after the play

#### Default reference pulse

| Pulse Name | Type | Amplitude | Length | Sigma | Axis Angle (IQ/MW) | Axis Angle (SingleChannel) |
|------------|------|-----------|--------|-------|---------------------|---------------------------|
| `gaussian` | `GaussianPulse` | 1.0 | 1000 ns | 167 ns | 0.0 | `None` |

Pulse names are centralized in `DrivePulseName` (`StrEnum`) in `names.py`:
- `DrivePulseName.GAUSSIAN` = `"gaussian"` (default)
- `DrivePulseName.DRAG` = `"drag"` (user-registered)

To switch pulse type (e.g. Gaussian → DRAG):
1. Register the new pulse: `qubit.xy.operations[DrivePulseName.DRAG] = DragPulse(...)`
2. Update the macro: `qubit.macros[SingleQubitMacroName.XY_DRIVE].reference_pulse_name = DrivePulseName.DRAG`
3. All gate macros (x90, x180, y90, etc.) automatically use the new pulse.

### Sensor Dot Readout Pulses

For each sensor dot in `machine.sensor_dots` with a `readout_resonator`, a default `SquareReadoutPulse` named `"readout"` is added (length 2000 ns, amplitude 0.1).

### Pulse Override Schema

Pulse overrides use the same scoping as macro overrides, under a `pulses` key:

```toml
# Type-level: all LDQubits get a shorter gaussian pulse
[component_types.LDQubit.pulses]
gaussian = {type = "GaussianPulse", length = 500, amplitude = 0.3, sigma = 83}

# Instance-level: qubit q1 gets a custom gaussian
[instances."qubits.q1".pulses]
gaussian = {type = "GaussianPulse", length = 800, amplitude = 0.15, sigma = 133}

# Remove a pulse
[instances."qubits.q2".pulses]
gaussian = {enabled = false}
```

Supported pulse types: `GaussianPulse`, `SquarePulse`, `SquareReadoutPulse`, `DragPulse`.

Precedence (last wins): default → type-level override → instance-level override.

Python runtime overrides use the typed helpers:

```python
from quam_builder.architecture.quantum_dots.macro_engine import (
    wire_machine_macros, pulse, overrides,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit

wire_machine_macros(
    machine,
    component_overrides={
        LDQubit: overrides(pulses={
            "gaussian": pulse("GaussianPulse", length=500, amplitude=0.3, sigma=83),
        }),
    },
    instance_overrides={
        "qubits.q1": overrides(pulses={
            "gaussian": pulse("GaussianPulse", length=800, amplitude=0.15, sigma=133),
        }),
    },
)
```

### Pulse Registry (Advanced)

For custom component types that need default pulses, use the pulse registry directly:

```python
from quam_builder.architecture.quantum_dots.operations.pulse_registry import (
    register_component_pulse_factories,
)
from quam.components.pulses import SquarePulse

register_component_pulse_factories(
    MyCustomComponent,
    {"drive": lambda: SquarePulse(length=200, amplitude=0.5)},
)
```

The registry follows MRO resolution: derived classes can override individual pulse names registered on a base class.

## Public APIs

Register macro defaults for a custom component type:

```python
from quam_builder.architecture.quantum_dots.operations.macro_registry import (
    register_component_macro_factories,
)

register_component_macro_factories(MyComponent, {"my_macro": MyMacroClass})
```

Register pulse defaults for a custom component type:

```python
from quam_builder.architecture.quantum_dots.operations.pulse_registry import (
    register_component_pulse_factories,
)

register_component_pulse_factories(MyComponent, {"drive": lambda: SquarePulse(length=200, amplitude=0.5)})
```

Wire defaults + overrides (macros and pulses):

```python
from quam_builder.architecture.quantum_dots.macro_engine import (
    wire_machine_macros, macro, pulse, overrides,
)
from quam_builder.architecture.quantum_dots.qubit import LDQubit

wire_machine_macros(
    machine,
    macro_profile_path="macros.toml",           # optional TOML profile
    component_overrides={                        # all instances of a type
        LDQubit: overrides(macros={...}, pulses={...}),
    },
    instance_overrides={                         # one specific instance
        "qubits.q1": overrides(macros={...}),
    },
    strict=True,
)
```

Builder integration:

- `build_base_quam(...)`
- `build_loss_divincenzo_quam(...)`
- `build_quam(...)`

all accept `macro_profile_path`, `component_overrides`, and `instance_overrides`.

## End-to-End Example

See [`../examples/default_macro_overrides_example.py`](../examples/default_macro_overrides_example.py) for:

1. default macro wiring
2. one-macro instance override
3. type-level override
4. program build using default + overridden macros

See [`../examples/default_macro_defaults_example.py`](../examples/default_macro_defaults_example.py) for:

1. default-only wiring (no profile and no runtime overrides)
2. parameterizing built-in default macro instances on components
3. program build using parameterized default macros only

See [`../examples/pulse_overrides_example.py`](../examples/pulse_overrides_example.py) for:

1. default pulse wiring via `wire_machine_macros`
2. type-level pulse overrides (all qubits of a type)
3. instance-level pulse overrides (one specific qubit)

See [`../examples/full_workflow_example.py`](../examples/full_workflow_example.py) for:

1. wiring a Loss-DiVincenzo qubit machine (combined single-stage workflow)
2. wiring default macros and pulses
3. updating operation parameters
4. swapping drive pulse type (Gaussian → DRAG)
5. replacing macros (instance-level and type-level overrides)
