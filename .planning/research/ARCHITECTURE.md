# Architecture Research

**Domain:** Quantum dot macro system — completing QuantumDot/SensorDot/QuantumDotPair integration
**Researched:** 2026-03-03
**Confidence:** HIGH (derived entirely from reading the live codebase on the active branch)

---

## System Overview

The quantum dots macro system is a layered, config-driven architecture that wires
named QUA behaviors (macros) onto components without coupling macro logic to
component class definitions.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Customer / Experiment Layer                           │
│                                                                              │
│   wire_machine_macros(machine, macro_profile_path=..., macro_overrides=...)  │
│   component.initialize()  component.x180()  operations_registry.x180(q1)   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                        Macro Engine Layer                                    │
│                                                                              │
│   macro_engine/wiring.py                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  wire_machine_macros                                                 │   │
│   │    1. register_default_component_macro_factories()  (catalog)        │   │
│   │    2. load_macro_profile()  (TOML)                                   │   │
│   │    3. _deep_merge(profile, runtime overrides)                        │   │
│   │    4. ensure_default_macros() on each component                      │   │
│   │    5. apply component_types overrides                                │   │
│   │    6. apply instances overrides                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                        Registry / Catalog Layer                              │
│                                                                              │
│   operations/macro_registry.py          operations/component_macro_catalog.py│
│   ┌───────────────────────────────┐     ┌──────────────────────────────────┐ │
│   │ _COMPONENT_MACRO_FACTORIES    │     │ register_default_component_macro  │ │
│   │ {fully_qualified_class: {     │     │ _factories()                     │ │
│   │   "macro_name": MacroClass,   │     │                                  │ │
│   │ }}                            │     │ QPU      -> QPU_STATE_MACROS      │ │
│   │                               │     │ LDQubit  -> SINGLE_QUBIT_MACROS   │ │
│   │ get_default_macro_factories() │     │ LDQubitPair -> TWO_QUBIT_MACROS   │ │
│   │  (MRO-aware resolution)       │     │                                  │ │
│   └───────────────────────────────┘     │ [MISSING: QuantumDot,            │ │
│                                         │  SensorDot, QuantumDotPair]      │ │
│                                         └──────────────────────────────────┘ │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                        Macro Class Layer                                     │
│                                                                              │
│   operations/default_macros/                                                 │
│   ┌───────────────────────┐  ┌────────────────────────┐  ┌───────────────┐  │
│   │  state_macros.py      │  │  single_qubit_macros.py│  │two_qubit_macros│  │
│   │                       │  │                        │  │.py            │  │
│   │ InitializeStateMacro  │  │ Initialize1QMacro      │  │Initialize2QM  │  │
│   │ MeasureStateMacro     │  │ Measure1QMacro         │  │Measure2QM     │  │
│   │ EmptyStateMacro       │  │ Empty1QMacro           │  │Empty2QM       │  │
│   │ QPUInitializeMacro    │  │ XYDriveMacro           │  │CNOTMacro(stub)│  │
│   │ QPUMeasureMacro       │  │ XMacro, YMacro, ZMacro │  │CZMacro(stub)  │  │
│   │ QPUEmptyMacro         │  │ X180/X90/XNeg90Macro   │  │SwapMacro(stub)│  │
│   │ STATE_POINT_MACROS    │  │ Y180/Y90/YNeg90Macro   │  │ISwapMacro(stub│  │
│   │ QPU_STATE_MACROS      │  │ Z180/Z90Macro          │  │               │  │
│   └───────────────────────┘  │ IdentityMacro          │  └───────────────┘  │
│                               │ SINGLE_QUBIT_MACROS    │                     │
│                               └────────────────────────┘                     │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                        Component / Mixin Layer                               │
│                                                                              │
│   VoltageControlMixin                                                        │
│     └── VoltagePointMixin   (add_point, step_to_point, ramp_to_point)       │
│                                                                              │
│   MacroDispatchMixin        (macros dict, __getattr__, compiled dispatch,    │
│                              sticky-voltage tracking, ensure_default_macros) │
│                                                                              │
│   VoltageMacroMixin         (VoltagePointMixin + MacroDispatchMixin          │
│                              + fluent API: with_step_point, with_sequence…)  │
│                                                                              │
│   VoltageMacroMixin users:                                                   │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  ┌────────────┐ │
│   │  QPU         │  │  QuantumDot  │  │  QuantumDotPair  │  │  LDQubit   │ │
│   │  (VolMacro)  │  │  (VolMacro)  │  │  (VolMacro)      │  │  (VolMacro │ │
│   │              │  │              │  │                  │  │   + Qubit) │ │
│   └──────────────┘  └──────────────┘  └──────────────────┘  └────────────┘ │
│                            ▲                                                 │
│                     SensorDot (QuantumDot)                                   │
│                                                                              │
│                            LDQubitPair (VolMacro + QubitPair)                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

| Component | Responsibility | Status |
|-----------|---------------|--------|
| `MacroDispatchMixin` | Stores `macros` dict; exposes macros as methods via `__getattr__`; compiled-call cache; sticky-voltage tracking interception | Shipped |
| `VoltageMacroMixin` | Combines `VoltagePointMixin` + `MacroDispatchMixin` + fluent builder API (`with_step_point`, `with_sequence`, etc.) | Shipped |
| `MacroRegistry` (`macro_registry.py`) | Keyed by fully-qualified class name; MRO-aware resolution; independent of component classes | Shipped |
| `ComponentMacroCatalog` (`component_macro_catalog.py`) | Idempotent one-time registration; maps `QPU`, `LDQubit`, `LDQubitPair` to their default factory dicts | Shipped — **gap: QD/SD/QDP** |
| `wire_machine_macros` | Runtime entry point; loads TOML; merges overrides; iterates components; applies type then instance overrides | Shipped |
| `names.py` | Enum-backed canonical string names for voltage points and macro identifiers | Shipped |
| `state_macros.py` | `InitializeStateMacro`, `MeasureStateMacro`, `EmptyStateMacro`; QPU dispatch variants; `STATE_POINT_MACROS` constant | Shipped |
| `single_qubit_macros.py` | Full 1Q macro set (XYDrive, X/Y/Z, fixed-angle wrappers, Identity); `SINGLE_QUBIT_MACROS` constant | Shipped |
| `two_qubit_macros.py` | Placeholder 2Q macros (CNOT/CZ/SWAP/iSWAP) + state macros; `TWO_QUBIT_MACROS` constant | Shipped (stubs) |
| `default_operations.py` | `OperationsRegistry` facade; typed operation signatures for IDE autocomplete | Shipped — **role clarification needed** |
| `QuantumDot` | Voltage-only component (no XY); delegates voltage operations to `VoltageMacroMixin`; has `voltage_sequence` property | Shipped — **catalog missing** |
| `SensorDot` | Extends `QuantumDot`; adds `readout_resonator` and `measure()` method | Shipped — **catalog missing** |
| `QuantumDotPair` | Voltage-only pair; detuning axis; barrier gate; references two `QuantumDot`s and optional sensor dots | Shipped — **catalog missing** |
| `LDQubit` | Voltage + XY (`VoltageMacroMixin + Qubit`); delegates voltage ops through `quantum_dot.voltage_sequence` | Shipped |
| `LDQubitPair` | Voltage + qubit-pair (`VoltageMacroMixin + QubitPair`); delegates to `quantum_dot_pair` | Shipped |

---

## Integration Points: New vs Modified

### What Is New (not yet built)

**1. Catalog entries for QuantumDot, SensorDot, QuantumDotPair**

File: `operations/component_macro_catalog.py`

Currently `register_default_component_macro_factories()` only registers `QPU`, `LDQubit`,
`LDQubitPair`. Adding `QuantumDot`, `SensorDot`, and `QuantumDotPair` requires:

```
register_component_macro_factories(QuantumDot, STATE_POINT_MACROS)
register_component_macro_factories(SensorDot, STATE_POINT_MACROS)
register_component_macro_factories(QuantumDotPair, STATE_POINT_MACROS)
```

`STATE_POINT_MACROS` already exists in `state_macros.py`. It maps:
- `"initialize"` -> `InitializeStateMacro`
- `"measure"` -> `MeasureStateMacro`
- `"empty"` -> `EmptyStateMacro`

These are voltage-point-based macros. They work without `Qubit` inheritance because
`_owner_component()` resolves owner by checking for `step_to_point`/`call_macro` —
both of which are present on `VoltageMacroMixin`. `InitializeStateMacro.apply()`
calls `owner.ramp_to_point(...)` and `MeasureStateMacro.apply()` calls
`owner.step_to_point(...)`. `QuantumDot` and `QuantumDotPair` both inherit
`VoltagePointMixin`, so these calls resolve correctly.

**SensorDot shares the QuantumDot catalog entry via MRO.** Because `SensorDot`
extends `QuantumDot`, the MRO-aware resolver in `get_default_macro_factories()`
will pick up `QuantumDot`'s entry automatically when resolving for a `SensorDot`
instance. A separate `register_component_macro_factories(SensorDot, ...)` call is
only needed if `SensorDot` requires macros that differ from `QuantumDot`. For the
current scope (state macros only), registering `QuantumDot` is sufficient for
`SensorDot` as well. An explicit `SensorDot` registration can be added later if
`SensorDot`-specific defaults diverge (e.g., auto-wiring a `measure` macro that
dispatches to `readout_resonator.measure(...)`).

**2. Missing single-qubit macro wrappers**

File: `operations/default_macros/single_qubit_macros.py`

`SINGLE_QUBIT_MACROS` and `names.py` are complete. The missing piece is the
`XMacro`, `YMacro`, `ZMacro` base implementations and the fixed-angle wrapper
hierarchy. Reading the file shows these classes _are implemented_ (`XMacro`,
`YMacro`, `ZMacro`, `X180Macro`, etc. are all present and registered in
`SINGLE_QUBIT_MACROS`). The gap listed in PROJECT.md ("all single-qubit macro
wrappers fully implemented") may refer to validation testing or an earlier state
of the branch. Verify by running the test suite.

**3. OperationsRegistry role clarification**

File: `operations/default_operations.py`

`OperationsRegistry` is already instantiated (`operations_registry`) and all
operations are registered. The open question from PROJECT.md is whether
`operations_registry` should be imported at build time and attached to the machine,
or remain a standalone utility for experiment authors who prefer the functional
form `x180(q1)` instead of `q1.x180()`. No code changes are required — only a
documentation decision about when and whether to call `operations_registry.register_on(machine)`
(or equivalent QuAM API). This belongs in the tutorial, not in a code change.

**4. Customer-facing tutorial**

This is net-new documentation. The existing `README.md` in
`quam_builder/architecture/quantum_dots/operations/` is technical/reference material.
The tutorial (target audience: experiment authors customizing macros) should cover the
four workflows in `PROJECT.md` without duplicating the README. Suggested split:

- Technical README (already exists): internal API reference, override schema, class inventory
- Tutorial (new): four workflows from a user's perspective, minimal boilerplate, no schema details

**5. Test coverage for QuantumDot/SensorDot/QuantumDotPair macro defaults**

Currently `test_quantum_dot.py` tests voltage operations but does not assert that
`QuantumDot.macros` contains `initialize`, `measure`, `empty` after
`ensure_default_macros()`. New test file or additions to existing files needed.

---

### What Is Modified (existing code changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `operations/component_macro_catalog.py` | Modified | Add three `register_component_macro_factories` calls for `QuantumDot`, `SensorDot` (optional), `QuantumDotPair` |
| `macro_engine/wiring.py` | None required | `_iter_macro_components` already yields `quantum_dots`, `sensor_dots`, `quantum_dot_pairs` — they will be visited once registered |
| `operations/names.py` | None required | Enum entries and macro name tuples are complete |
| `operations/default_macros/state_macros.py` | None required | `STATE_POINT_MACROS` exists and is the correct constant to reuse |
| `operations/default_macros/single_qubit_macros.py` | Validate only | Classes appear complete; confirm by test run |
| `operations/default_operations.py` | Documentation only | Clarify import and usage guidance; no code changes |

---

## Recommended Project Structure

```
quam_builder/architecture/quantum_dots/
├── components/
│   ├── mixins/
│   │   ├── macro_dispatch.py      # MacroDispatchMixin — no changes needed
│   │   ├── voltage_macro.py       # VoltageMacroMixin — no changes needed
│   │   ├── voltage_point.py       # VoltagePointMixin — no changes needed
│   │   └── voltage_control.py     # VoltageControlMixin — no changes needed
│   ├── quantum_dot.py             # QuantumDot — no changes needed
│   ├── sensor_dot.py              # SensorDot — no changes needed
│   └── quantum_dot_pair.py        # QuantumDotPair — no changes needed
│
├── operations/
│   ├── component_macro_catalog.py # [MODIFY] Add QD/SD/QDP registration
│   ├── macro_registry.py          # No changes needed
│   ├── names.py                   # No changes needed
│   ├── default_operations.py      # [DOCUMENT] OperationsRegistry role
│   ├── default_macros/
│   │   ├── state_macros.py        # No changes needed (STATE_POINT_MACROS exists)
│   │   ├── single_qubit_macros.py # [VALIDATE] All wrappers present
│   │   └── two_qubit_macros.py    # No changes needed (stubs are intentional)
│   └── README.md                  # [UPDATE] Add QD/SD/QDP entries to component table
│
├── macro_engine/
│   └── wiring.py                  # No changes needed
│
├── examples/
│   └── [ADD] Tutorial examples    # Four customer workflow scripts
│
└── tests/
    ├── components/
    │   ├── test_quantum_dot.py     # [EXPAND] Add macro default assertions
    │   ├── test_sensor_dot.py      # [EXPAND] Add macro default assertions
    │   └── test_quantum_dot_pair.py# [EXPAND] Add macro default assertions
    └── builder/quantum_dots/
        └── test_macro_wiring.py    # [EXPAND] Add QD/SD/QDP wiring tests
```

---

## Architectural Patterns

### Pattern 1: MRO-Aware Default Resolution

**What:** `get_default_macro_factories(component)` walks the MRO from base to derived,
merging factory maps so that more-derived registrations override base registrations.
Utility macros (`align`, `wait`) from `UTILITY_MACRO_FACTORIES` are seeded first as the
lowest-priority layer.

**When to use:** Register at the most general applicable type. Do not register both
`QuantumDot` and `SensorDot` unless `SensorDot` genuinely needs different defaults.
MRO resolution handles inheritance automatically.

**Trade-offs:** Changing a base class registration affects all subclasses that do not
override. This is intentional and desirable for broad behavioral changes.

**Example:**
```python
# Registering QuantumDot is sufficient for SensorDot because SensorDot inherits QuantumDot.
register_component_macro_factories(QuantumDot, STATE_POINT_MACROS)
# SensorDot instances will resolve STATE_POINT_MACROS via MRO.
```

### Pattern 2: Additive Default Materialization

**What:** `MacroDispatchMixin.ensure_default_macros()` only inserts macros that are
absent from `self.macros`. It never overwrites existing entries. This means:
- Deserialized state (loaded from JSON) retains user-modified macro parameters.
- Calling `wire_machine_macros(machine)` after load is safe and idempotent for defaults.

**When to use:** Always the right behavior for defaults. Override entries via the
`wire_machine_macros` override schema when replacement is intended.

**Trade-offs:** A stale serialized macro class that no longer matches the default
will silently persist. The `wire_machine_macros` override mechanism is the escape
hatch.

### Pattern 3: Two-Level Override (Type then Instance)

**What:** `wire_machine_macros` applies overrides in two passes:
1. Component-type level — applies to all instances of matching type.
2. Instance level — applies to exactly one component by path.

Instance overrides always win over type overrides because they run last.

**When to use:** Type-level for lab-wide calibration defaults; instance-level for
device-specific tuning.

**Example:**
```python
wire_machine_macros(
    machine,
    macro_overrides={
        "component_types": {
            "QuantumDot": {"macros": {"initialize": {"factory": MyInitMacro, "params": {"ramp_duration": 32}}}},
        },
        "instances": {
            "quantum_dots.dot_2": {"macros": {"initialize": {"factory": MyInitMacro, "params": {"ramp_duration": 64}}}},
        },
    },
)
```

### Pattern 4: Serializable Macro State

**What:** All macro objects stored in `component.macros` are `@quam_dataclass`-decorated
`QuamMacro` subclasses. Their fields are serialized as part of the QuAM state JSON.
Runtime caches (`_DISPATCH_CACHE`, `_WARNED_MACRO_KEYS`) are `WeakKeyDictionary`
instances and are never serialized.

**When to use:** Every custom macro class must use `@quam_dataclass`. Fields that are
runtime-only (not needed for reconstruction) should be excluded with `ClassVar` or
excluded from serialization.

**Example:**
```python
@quam_dataclass
class MyMacro(QuamMacro):
    ramp_duration: int = 32
    updates_voltage_tracking: ClassVar[bool] = True  # ClassVar excluded from serialization
```

---

## Data Flow

### Macro Wiring Flow (at build / load time)

```
wire_machine_macros(machine)
    │
    ├── register_default_component_macro_factories()
    │       (idempotent; QPU, LDQubit, LDQubitPair already registered)
    │       [AFTER MILESTONE: also QuantumDot, QuantumDotPair]
    │
    ├── load_macro_profile(path)  ->  profile_data dict
    │
    ├── _deep_merge(profile_data, runtime_overrides)  ->  merged_overrides
    │
    ├── _iter_macro_components(machine)
    │       yields: quantum_dots.*, sensor_dots.*, barrier_gates.*,
    │               global_gates.*, quantum_dot_pairs.*, qubits.*, qubit_pairs.*, qpu
    │
    ├── for each component: ensure_default_macros()
    │       calls get_default_macro_factories(component)
    │           [utility defaults] + [MRO-resolved type defaults]
    │       inserts missing entries into component.macros
    │
    ├── apply component_types overrides
    │       for each component: match by type name / FQN
    │       _apply_macros_to_component(component, macros_config)
    │
    └── apply instances overrides
            for each path in merged_overrides["instances"]
            _apply_macros_to_component(components_by_path[path], macros_config)
```

### Macro Execution Flow (inside QUA program)

```
component.initialize()
    │
    └── __getattr__("initialize")
            → _get_compiled_macro_callable("initialize")
                → cache miss: _compile_macro_callable(macro)
                    → returns _call(**kwargs) closure
                    → cache[(macro_name)] = (macro, _call)
            → _call()
                → _execute_macro_with_sticky_tracking(macro)
                    → macro.apply()
                        (e.g., InitializeStateMacro.apply())
                        → owner.ramp_to_point("initialize", ramp_duration=16)
                    → if not updates_voltage_tracking:
                        voltage_sequence.track_sticky_duration(duration_ns)
```

### QPU Dispatch Flow

```
machine.qpu.initialize()
    │
    └── QPUInitializeMacro.apply()
            → _iter_qpu_targets(machine)
                  priority 1: machine.active_qubit_names → machine.qubits[name]
                  priority 2: all machine.qubits.values()
                  priority 3 (fallback): machine.quantum_dots.values()
                  then: qubit_pairs / quantum_dot_pairs analogously
            → for each component: component.call_macro("initialize")
```

Note: The QPU fallback to `machine.quantum_dots` in `_iter_qpu_targets` means that even
before `QuantumDot` is registered in the catalog, `QPUInitializeMacro` will try to call
`initialize` on each `QuantumDot`. This currently fails with a `KeyError` because
`QuantumDot.macros` does not contain `"initialize"`. Registering `QuantumDot` in the
catalog fixes this silently and correctly.

---

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `component_macro_catalog.py` -> `macro_registry.py` | Direct call to `register_component_macro_factories()` | Lazy import inside `register_default_component_macro_factories()` avoids circular import |
| `MacroDispatchMixin.__post_init__` -> `component_macro_catalog.py` | Calls `register_default_component_macro_factories()` on construction | Idempotent guard (`_REGISTERED`) prevents re-registration |
| `wire_machine_macros` -> `MacroDispatchMixin` | Calls `component.ensure_default_macros()`, `component.set_macro()` | `set_macro` also invalidates the dispatch cache |
| `InitializeStateMacro.apply()` -> `VoltageMacroMixin` | Calls `owner.ramp_to_point()` | Owner resolved via `_owner_component()` heuristic (checks for `step_to_point` or `call_macro`) |
| `_iter_macro_components` -> `BaseQuamQD` | Reads named collections (`quantum_dots`, `sensor_dots`, etc.) | Already includes `quantum_dots`, `sensor_dots`, `quantum_dot_pairs` — no changes needed |
| `default_operations.py` (`OperationsRegistry`) -> `MacroDispatchMixin` | `OperationsRegistry` dispatches to `component.macros[operation_name]` at runtime | `operations_registry` is a module-level singleton; attach to machine or use standalone |

### Type Constraint: `QubitMacro` vs `QuamMacro`

`LDQubit`-specific macros (`Initialize1QMacro`, `Measure1QMacro`, etc.) inherit
`QubitMacro`, which provides `self.qubit` as a typed accessor to the owning qubit.
`QuantumDot`, `SensorDot`, `QuantumDotPair` do not inherit `Qubit`, so they cannot use
`QubitMacro` directly. They must use `QuamMacro` as their base class, resolving the
owner via `_owner_component(self)` (already the pattern in `state_macros.py`). This is
why `InitializeStateMacro`, `MeasureStateMacro`, `EmptyStateMacro` use the `_owner_component`
helper rather than `self.qubit`, making them correctly reusable for both voltage-only and
qubit component types.

---

## Build Order for Completing the Milestone

The following order respects dependencies between steps:

**Step 1 — Catalog registration (single file change, ~3 lines)**

Modify `operations/component_macro_catalog.py`:
- Add lazy imports for `QuantumDot`, `QuantumDotPair`.
- Add `register_component_macro_factories(QuantumDot, STATE_POINT_MACROS)`.
- Add `register_component_macro_factories(QuantumDotPair, STATE_POINT_MACROS)`.
- Do NOT add a separate `SensorDot` entry unless tests reveal it is needed.

This is the single highest-leverage change in the milestone. It unblocks QPU dispatch,
enables QD/QDP defaults, and fixes the `_iter_qpu_targets` fallback path.

**Step 2 — Test coverage for QD/SD/QDP macro defaults**

Add assertions to `tests/architecture/quantum_dots/components/`:
- `test_quantum_dot.py`: after `wire_machine_macros(machine)` or
  `qd.ensure_default_macros()`, assert `"initialize"`, `"measure"`, `"empty"` in `qd.macros`.
- `test_sensor_dot.py`: same assertions (verify MRO-based resolution works).
- `test_quantum_dot_pair.py`: same assertions.

Also add to `tests/builder/quantum_dots/test_macro_wiring.py`:
- Test that `component_types.QuantumDot` overrides propagate to all `quantum_dots.*` instances.
- Test that `instances.quantum_dots.dot_1` overrides target exactly one instance.

**Step 3 — Validate single-qubit macro wrappers**

Run `make test` and confirm `tests/builder/quantum_dots/test_macro_wiring.py` and
`tests/builder/quantum_dots/test_macro_names.py` pass. If any single-qubit wrapper
class is missing from `SINGLE_QUBIT_MACROS`, add it; otherwise no code change is needed.

**Step 4 — OperationsRegistry role documentation**

In `operations/default_operations.py`, add a module-level docstring or short comment
block clarifying:
- `operations_registry` is a module-level singleton.
- Use `component.macro_name()` for direct dispatch (no import required).
- Use `operations_registry.macro_name(component)` for the functional style (requires import).
- No code change required in the registry itself.

Update `operations/README.md` to add `QuantumDot`, `SensorDot`, `QuantumDotPair` to
the "Default Macro Logic by Component Type" table.

**Step 5 — Tutorial documentation**

Create a new tutorial file (location TBD by milestone roadmap) covering the four
customer workflows:
1. Use defaults out of the box (call `wire_machine_macros(machine)`; access `qd.initialize()`).
2. Edit defaults globally (use `component_types.QuantumDot` override).
3. Override per component (use `instances.quantum_dots.dot_1` override).
4. Bring an external macro package (use `build_macro_overrides()` pattern from README).

Do not duplicate the technical README. Link to it for schema reference.

---

## Anti-Patterns

### Anti-Pattern 1: Register SensorDot Separately Without a Real Divergence

**What people do:** Add `register_component_macro_factories(SensorDot, STATE_POINT_MACROS)`
in addition to the `QuantumDot` registration.

**Why it's wrong:** `SensorDot` inherits `QuantumDot`. MRO resolution already gives
`SensorDot` instances the `QuantumDot` defaults. Duplicating the registration is
harmless but adds maintenance burden and misleads future readers into thinking `SensorDot`
has distinct defaults.

**Do this instead:** Only add a `SensorDot` catalog entry when `SensorDot` needs macros
that are genuinely different from `QuantumDot` defaults (e.g., a `measure` macro that
calls `readout_resonator.measure()`).

### Anti-Pattern 2: Subclassing QubitMacro for QuantumDot Macros

**What people do:** Create `QuantumDotInitializeMacro(InitializeStateMacro, QubitMacro)`
to get `self.qubit` on a `QuantumDot`.

**Why it's wrong:** `QuantumDot` does not inherit `Qubit`. QuAM will not set `self.qubit`
correctly and the macro will raise an `AttributeError` at runtime. The existing
`_owner_component()` pattern in `state_macros.py` is the correct approach for
voltage-only components.

**Do this instead:** Use `QuamMacro` as the base and resolve the owner via
`_owner_component(self)`. For `LDQubit`-specific variants that need `self.qubit`,
use `QubitMacro` — but only in `single_qubit_macros.py` where `LDQubit` is the target.

### Anti-Pattern 3: Coupling OperationsRegistry to Machine Construction

**What people do:** Call `operations_registry.register_on(machine)` or equivalent
inside `wire_machine_macros`, making the registry mandatory for every machine.

**Why it's wrong:** `OperationsRegistry` is optional infrastructure for experiment
authors who prefer functional-style operation dispatch. Most users will access macros
directly via `component.initialize()`. Mandatory coupling inflates the API surface and
creates an unexpected import dependency.

**Do this instead:** Document `OperationsRegistry` as an opt-in tool. Keep
`wire_machine_macros` focused on macro materialization and override application.

### Anti-Pattern 4: Modifying component.macros Dict Directly in Wire Logic

**What people do:** Write `component.macros["initialize"] = MyMacro()` inside
`wire_machine_macros` instead of using `_set_component_macro()`.

**Why it's wrong:** Direct dict mutation skips the dispatch cache invalidation in
`_invalidate_macro_dispatch()`. The old compiled callable remains in cache and the
new macro is never executed.

**Do this instead:** Always use `_set_component_macro(component, name, macro)` inside
`wire_machine_macros`, or `component.set_macro(name, macro)` from user code.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Integration points (what touches what) | HIGH | Verified from live source files |
| New vs modified (catalog gap) | HIGH | Confirmed by reading `component_macro_catalog.py` directly |
| Build order | HIGH | Dependencies derived from reading actual import chains |
| `SensorDot` MRO behavior | HIGH | `get_default_macro_factories` MRO walk is explicit in `macro_registry.py` |
| `OperationsRegistry` role | HIGH | `default_operations.py` and README are authoritative |
| Single-qubit wrapper completeness | MEDIUM | Classes visible in code but test run needed to confirm nothing is missing |
| Tutorial structure recommendation | MEDIUM | Based on reading existing docs and examples; authoring details depend on milestone roadmap |

---

*Architecture research for: quam-builder — QD Operations milestone*
*Researched: 2026-03-03*
