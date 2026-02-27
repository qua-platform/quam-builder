# Quantum Dots Operations and Macro Defaults

This folder contains the default operations + macro wiring system for quantum-dot QuAM components.
The main goal is to keep macro behavior decoupled from component classes while making defaults and user overrides explicit, composable, and serializable.

## Architecture Overview

Core modules:

- [`names.py`](./names.py): canonical string names (voltage points and macro names).
- [`default_macros/`](./default_macros): built-in macro classes and default per-component macro maps.
- [`macro_registry.py`](./macro_registry.py): component-type -> default macro factory registration/resolution.
- [`component_macro_catalog.py`](./component_macro_catalog.py): idempotent registration of architecture defaults (`QPU`, `LDQubit`, `LDQubitPair`).
- [`../macro_engine/wiring.py`](../macro_engine/wiring.py): runtime wiring API (`wire_machine_macros`) that materializes defaults and applies overrides.
- [`default_operations.py`](./default_operations.py): operation signatures exposed through `OperationsRegistry`.

## Canonical Voltage Point Enums

Voltage-point names are centralized in [`names.py`](./names.py):

- `initialize`
- `measure`
- `empty`

These are represented by `VoltagePointName` (`StrEnum`) and reused by default state macros.
Default state macros assume these points exist in each relevant voltage sequence (for example via `with_step_point(...)`).

Canonical macro names are also centralized as enums in the same module:

- `SingleQubitMacroName` for built-in 1Q defaults (`xy_drive`, `x`, `y`, `z`, `x180`, ...)
- `TwoQubitMacroName` for built-in 2Q defaults (`cnot`, `cz`, `swap`, `iswap`)

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

- State macros: `initialize`, `measure`, `empty`
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

- State macros: `initialize`, `measure`, `empty`
- Two-qubit gates: `cnot`, `cz`, `swap`, `iswap`

Default two-qubit gate macros are explicit placeholders (`NotImplementedError`) until user calibration logic is supplied through overrides.

## When and Where Macros Are Wired

Wiring happens in three places:

1. Component construction (`MacroDispatchMixin.__post_init__`): materializes missing defaults.
2. Build flow (`build_base_quam`, `build_loss_divincenzo_quam`, `build_quam`): calls `wire_machine_macros(...)`.
3. Load flow (`BaseQuamQD.load`, `LossDiVincenzoQuam.load`): calls `wire_machine_macros(instance)` after load.

Important behavior:

- Default materialization is additive: only missing default macro names are inserted.
- Existing macro entries are not reset unless an override explicitly targets that name.

## Override Model (Detailed)

`wire_machine_macros(machine, macro_profile_path=..., macro_overrides=..., strict=True)` supports two override scopes:

- `component_types.<TypeKey>.macros.<macro_name>`
- `instances.<component_path>.macros.<macro_name>`

### Precedence and Merge Order

1. Architecture defaults (registry/catalog).
2. TOML profile from `macro_profile_path`.
3. Runtime mapping from `macro_overrides` (deep-merged over profile).
4. Type-level overrides applied to each matching instance.
5. Instance-level overrides applied last.

So, effective precedence for a specific macro name on one component is:

`instance override` > `type override` > `runtime/profile config` > `default`.

### Targeting Component Types

Type override keys may use either:

- short class name, e.g. `LDQubit`
- fully qualified class name, e.g. `quam_builder.architecture.quantum_dots.qubit.LDQubit`

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

### Macro Entry Forms

These forms are the values of `macros.<macro_name>` entries inside either:

- TOML profile loaded by `macro_profile_path`
- Python runtime mapping passed as `macro_overrides`

In TOML, they live under:

```toml
[component_types.<TypeKey>.macros]
[instances."<component_path>".macros]
```

In Python, they live under:

```python
{
  "component_types": {"<TypeKey>": {"macros": {...}}},
  "instances": {"<component_path>": {"macros": {...}}},
}
```

Each `macros.<macro_name>` entry can be one of:

1. Full mapping:

```toml
[component_types.LDQubit.macros.initialize]
factory = "my_pkg.macros:CustomInitializeMacro"
enabled = true
[component_types.LDQubit.macros.initialize.params]
ramp_duration = 64
```

2. Path-string shorthand:

```toml
[component_types.LDQubitPair.macros]
cz = "my_pkg.macros:CalibratedCZMacro"
```

3. Python class shorthand (runtime mapping only):

```python
{"factory": CustomMacroClass}
# or simply:
CustomMacroClass
```

`factory` requirements:

- Must resolve to a `QuamMacro` subclass.
- String format must be `"module.path:ClassName"`.

### Disable/Remove a Macro

Use `enabled = false`:

```toml
[instances."qubit_pairs.q1_q2".macros.cz]
enabled = false
```

This removes the macro from that component’s `macros` mapping.

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
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros

wire_machine_macros(
    machine,
    macro_overrides={
        "instances": {
            "qubits.q1": {
                "macros": {
                    "x180": {
                        "factory": "my_pkg.macros:TunedX180Macro",
                        "params": {"default_amplitude_scale": 0.78},
                    }
                }
            }
        }
    },
    strict=True,
)
```

Result:

- `qubits.q1.macros["x180"]` is replaced.
- `qubits.q1` all other macro names are untouched.
- all macros on other qubits are untouched.

## Type-Level Override + Instance-Level Specialization

Pattern: set lab-wide default for a component type, then specialize one device instance.

```python
wire_machine_macros(
    machine,
    macro_overrides={
        "component_types": {
            "LDQubit": {
                "macros": {
                    "initialize": {
                        "factory": "my_pkg.macros:InitMacro",
                        "params": {"ramp_duration": 64},
                    }
                }
            }
        },
        "instances": {
            "qubits.q2": {
                "macros": {
                    "initialize": {
                        "factory": "my_pkg.macros:InitMacro",
                        "params": {"ramp_duration": 96},
                    }
                }
            }
        },
    },
)
```

`qubits.q2` wins over type-level settings because instance overrides are applied last.

## Profile + Runtime Combination

Typical workflow:

1. Keep stable, shared calibration defaults in TOML (`macro_profile_path`).
2. Apply session-specific tweaks with `macro_overrides` in Python.

Because runtime overrides are deep-merged over profile data, users can patch only one leaf value without duplicating the full profile map.

## Importing a Full Macro Catalog From Another Package

For users who want a custom default set that survives upstream pulls, keep macro logic in a separate package/repo and import it in Python as `macro_overrides`.

### Where This Should Sit

Use this layout:

1. External package (stable lab-owned code): `my_lab_qd_macros/`
2. Experiment/build entrypoint (in your experiment repo): where `build_quam(...)` is called
3. Optional local TOML for small per-run tweaks

### External package example

`my_lab_qd_macros/catalog.py`:

```python
from __future__ import annotations

from quam_builder.architecture.quantum_dots.operations.default_macros.single_qubit_macros import (
    XYDriveMacro,
)
from .single_qubit import LabInitialize1Q, LabMeasure1Q, LabEmpty1Q, LabX, LabY, LabZ
from .two_qubit import LabCZ, LabISWAP, LabCNOT, LabSWAP
from .qpu import LabInitializeQPU, LabMeasureQPU, LabEmptyQPU


def build_macro_overrides() -> dict:
    return {
        "component_types": {
            "QPU": {
                "macros": {
                    "initialize": {"factory": LabInitializeQPU},
                    "measure": {"factory": LabMeasureQPU},
                    "empty": {"factory": LabEmptyQPU},
                }
            },
            "LDQubit": {
                "macros": {
                    "initialize": {"factory": LabInitialize1Q},
                    "measure": {"factory": LabMeasure1Q},
                    "empty": {"factory": LabEmpty1Q},
                    "xy_drive": {"factory": XYDriveMacro, "params": {"max_amplitude_scale": 0.85}},
                    "x": {"factory": LabX},
                    "y": {"factory": LabY},
                    "z": {"factory": LabZ},
                }
            },
            "LDQubitPair": {
                "macros": {
                    "cnot": {"factory": LabCNOT},
                    "cz": {"factory": LabCZ},
                    "swap": {"factory": LabSWAP},
                    "iswap": {"factory": LabISWAP},
                }
            },
        }
    }
```

### Experiment call site example

In your experiment repo, at the machine-build call site:

```python
from quam_builder.builder.quantum_dots import build_quam
from my_lab_qd_macros.catalog import build_macro_overrides

machine = build_quam(
    machine=machine,
    macro_overrides=build_macro_overrides(),
)
```

This keeps custom defaults out of `quam-builder` itself, so pulling upstream changes does not overwrite your catalog.

### Optional pattern: catalog defaults + local one-off tweak

```python
from my_lab_qd_macros.catalog import build_macro_overrides
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros

overrides = build_macro_overrides()
overrides["instances"] = {
    "qubits.q3": {
        "macros": {
            "x180": {"factory": "my_lab_qd_macros.single_qubit:Q3TunedX180"}
        }
    }
}
wire_machine_macros(machine, macro_overrides=overrides, strict=True)
```

This is the recommended model for common lab usage: central catalog + selective per-device override.

## Calibrated Parameters: Storage and Persistence

There are two storage layers:

1. Source-of-truth config (optional):
   - TOML profile in your repository/lab config.
2. Runtime QuAM object:
   - instantiated macro objects in `component.macros`.

Macro parameter examples:

- `machine.qubits["q1"].macros["initialize"].ramp_duration`
- `machine.qubits["q1"].macros["xy_drive"].max_amplitude_scale`

Serialization behavior:

- Macro objects/fields in `component.macros` are part of QuAM state.
- Runtime dispatch caches are not serialized (by design).

## Recommended Override Strategy

1. Override canonical macros first (`xy_drive`, `x`, `y`, `z`) if you want broad behavioral changes.
2. Override wrapper macros (`x90`, `x180`, etc.) only for fixed-angle special cases.
3. Keep two-qubit calibrated logic in profile/type-level overrides and specialize only exceptional instances.
4. Use `strict=True` for CI and release configs.

## Sticky-Voltage Tracking Compatibility

Macro dispatch still goes through [`../components/mixins/macro_dispatch.py`](../components/mixins/macro_dispatch.py), so sticky-voltage tracking remains active:

- Voltage-updating macros should set `updates_voltage_tracking = True`.
- Non-voltage macros should expose `inferred_duration` (seconds), quantized to 4 ns downstream.

This preserves non-voltage hold-time tracking with the current macro call path.

## Public APIs

Register defaults for a custom component type:

```python
from quam_builder.architecture.quantum_dots.operations.macro_registry import (
    register_component_macro_factories,
)

register_component_macro_factories(MyComponent, {"my_macro": MyMacroClass})
```

Wire defaults + overrides:

```python
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros

wire_machine_macros(
    machine,
    macro_profile_path="macros.toml",
    macro_overrides={"instances": {"qubits.q1": {"macros": {...}}}},
    strict=True,
)
```

Builder integration:

- `build_base_quam(...)`
- `build_loss_divincenzo_quam(...)`
- `build_quam(...)`

all accept `macro_profile_path` and `macro_overrides`.

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
