# Feature Research

**Domain:** Python physics-hardware library — plugin/override customization system for quantum dots
**Researched:** 2026-03-03
**Confidence:** HIGH (all findings derived from direct codebase analysis)

---

## Context: What Is Already Built

The milestone continues an in-progress branch. Understanding what already exists prevents
re-implementing or conflicting with shipped code.

**Already complete (do not rebuild):**

- `wire_machine_macros(machine, macro_profile_path=..., macro_overrides=...)` — runtime entry point
- TOML profile + Python dict runtime overrides merged with deep-merge semantics
- `component_types.<TypeName>.macros` and `instances.<collection.id>.macros` override schema
- `MacroDispatchMixin` — `macros` dict, compiled-callable cache, `__getattr__` dispatch, sticky tracking
- `VoltageMacroMixin` — fluent `.with_step_point()/.with_ramp_point()/.with_sequence()` API
- `InitializeStateMacro`, `MeasureStateMacro`, `EmptyStateMacro` — fully implemented, shared
- `XYDriveMacro`, `XMacro`, `YMacro`, `ZMacro`, `X180Macro`...`Z90Macro`, `IdentityMacro` — fully implemented for `LDQubit`
- `_QPUStateDispatchMacro` / `QPUInitializeMacro/Measure/Empty` — machine-level dispatch
- `register_component_macro_factories()` / `get_default_macro_factories()` with MRO resolution
- `register_default_component_macro_factories()` — already registers `QPU`, `LDQubit`, `LDQubitPair`
- `OperationsRegistry` with all operations registered in `default_operations.py`
- `names.py` — `StrEnum`-backed canonical names for everything
- Two working examples: `default_macro_defaults_example.py`, `default_macro_overrides_example.py`

**Gap in the catalog (the actual work):**

`QuantumDot`, `SensorDot`, and `QuantumDotPair` already inherit `VoltageMacroMixin` → `MacroDispatchMixin`
and call `ensure_default_macros()` in `__post_init__`. But `register_default_component_macro_factories()`
does not register them, so they only receive utility macros (align, wait) from `UTILITY_MACRO_FACTORIES`.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these means the product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `QuantumDot` default state macros (initialize/measure/empty) | QuantumDot is the core voltage-only component; every user experiment touches it; state transitions are the first thing they write | LOW | `STATE_POINT_MACROS` dict already exists in `state_macros.py`. Registration is a three-line addition to `component_macro_catalog.py`. No new macro classes required. |
| `SensorDot` default state macros | SensorDot inherits QuantumDot; same voltage workflow; readout path differs but state-prep is identical | LOW | `SensorDot` should register separately from `QuantumDot` so MRO resolution produces correct inherited behavior. `STATE_POINT_MACROS` applies directly. |
| `QuantumDotPair` default state macros | QuantumDotPair holds two dots plus barrier gate; all pair-level experiments begin with initialize/empty; absence is a glaring gap | LOW | Already has `step_to_point`/`ramp_to_point` via `VoltageMacroMixin`. `STATE_POINT_MACROS` applies; no XY macros on pairs (voltage-only by design). |
| `QuantumDot/SensorDot/QuantumDotPair` absent from `_iter_macro_components` iteration | `wire_machine_macros` currently only iterates `quantum_dots`, `sensor_dots`, `quantum_dot_pairs`, `qubits`, `qubit_pairs`. The iteration list exists; the catalog registration is what is missing. | LOW | `_iter_macro_components` in `wiring.py` already includes `"quantum_dots"`, `"sensor_dots"`, `"quantum_dot_pairs"` — they are iterated, just never find registered factories. Registration fills this automatically. |
| Test coverage for new component registrations | No tests exist for `QuantumDot`/`SensorDot`/`QuantumDotPair` macro defaults. Regression risk is real. | LOW | Mirror the existing test patterns in `test_macro_wiring.py`. Fixture machines with these components are available in the test conftest. |
| XMacro/YMacro/ZMacro delegation chain is complete and working | Users calling `qubit.x(angle=np.pi/4)` expect it to reach `xy_drive` correctly; the wrapper chain must not break on missing intermediate macros | LOW | Already implemented. `_AxisRotationMacro` → `xy_drive` delegation and `_FixedAxisAngleMacro` → canonical axis delegation are both complete in `single_qubit_macros.py`. No new code required — only verification in tests. |
| `OperationsRegistry` correctly typed for voltage-only components | `OperationsRegistry` in `default_operations.py` types `initialize/measure/empty` to `QuantumComponent`; voltage-only components like `QuantumDot` are `QuantumComponent`. This already works. | LOW | Confirm that voltage-only components can be dispatched through the registry without type errors. `QuantumDot` inherits `VoltageMacroMixin` which inherits `MacroDispatchMixin` which inherits `QuantumComponent`. |
| Tutorial covering all four override workflows | Customers cannot discover the system without a guide. The two existing examples are code demos, not a tutorial. | MEDIUM | Requires deliberate structure: concepts first, then four progressive workflows, each with a minimal working snippet. The existing examples are source material, not the tutorial itself. |

### Differentiators (Competitive Advantage)

Features that distinguish this system from ad-hoc macro management.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| TOML profile as stable lab config | Labs can commit a TOML file that captures calibrated macro parameters; Python runtime overrides handle session-specific tweaks. Separation is meaningful for reproducibility. | LOW (design complete, already in `wiring.py`) | The tutorial must explain this split explicitly. Users who grasp it will adopt it; users who do not will use Python-only overrides and lose the reproducibility benefit. |
| MRO-aware factory resolution | Subclass hierarchy (SensorDot inherits QuantumDot) resolves macros correctly without user intervention. Users can register at any level of the hierarchy. | LOW (already in `get_default_macro_factories`) | Tutorial should illustrate why registering at `QuantumDot` level auto-applies to `SensorDot` via MRO without extra registration. |
| Two-level delegation chain (xy_drive → x/y/z → x180/x90) | Users who replace only `xy_drive` get correct behavior for all fixed-angle wrappers automatically. No per-angle overrides needed. | LOW (already implemented) | Tutorial must make this visible. Show: "Override xy_drive, all rotation wrappers update." |
| Post-build dict mutation escape hatch (`component.macros["x180"] = MyMacro()`) | Advanced users can mutate macros after `wire_machine_macros()` without re-running the entire wiring step. | LOW (MacroDispatchMixin handles invalidation) | Document as Workflow 4 escape hatch pattern, not primary workflow. Mark as advanced. |
| Serialization compatibility of all macro state | Macro objects stored in `component.macros` survive QuAM save/load cycles because all macro classes use `@quam_dataclass`. | MEDIUM (design constraint, not new feature) | Tutorial must mention this as a constraint on custom macro classes: always use `@quam_dataclass`. Failure to do so causes silent state loss on save/load. |
| `OperationsRegistry` as typed operations facade | `operations_registry.initialize(component)` provides a type-annotated call site separate from the low-level `component.macros["initialize"].apply()`. Enables IDE completion and static checking. | LOW (already exists in `default_operations.py`) | Tutorial should clarify when to use `operations_registry` vs direct macro calls. Current recommendation: `operations_registry` for QUA programs, direct macro access for parameterization. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Global mutable macro registry with process-wide defaults | "Make it just work without calling wire_machine_macros" | Breaks testability (tests see each other's registrations), breaks serialization (global state not in QuAM graph), impossible to scope per-machine | The existing design is correct: `wire_machine_macros()` is explicit and per-machine. Tutorial must explain why this is intentional. |
| Auto-registration from class decorators (`@register_macros`) | Reduces boilerplate | Causes import-order sensitivity and circular import risk (same pattern is already avoided in `MacroDispatchMixin` via lazy import guards). Makes registration invisible, debugging harder. | Explicit `register_default_component_macro_factories()` call at wiring time is the right pattern. |
| XY-drive macros on QuantumDot/SensorDot/QuantumDotPair | "Add XY gates to all component types" | QuantumDot, SensorDot, QuantumDotPair have no XY drive channel — they are voltage-only by design. Adding XY macros to them would make them silently fail or require a channel that does not exist. | Only LDQubit has an `xy` channel. XY macros belong only to the `LDQubit`/`LDQubitPair` catalog. |
| Merging QuantumDot macros into LDQubit macros | "DRY: one registration covers both" | LDQubit already has all state macros via its own registration. QuantumDot is a separate component type with different `voltage_sequence` resolution. MRO ensures LDQubit inherits QuantumDot registrations if QuantumDot is registered first — but this dependency is fragile unless clearly documented. | Register `QuantumDot` separately. MRO resolution handles the inheritance automatically. |
| Validate macro class types at registration time | "Catch wrong macro types early" | The `register_component_macro_factories()` function accepts any class mapping. Adding type enforcement couples the registry to specific macro base classes, making it harder to use framework-agnostic or mock factories in tests. | Trust the existing `_resolve_macro_factory()` in `wiring.py` which validates `QuamMacro` subclass at wire time — after factories are resolved but before instantiation. |
| Tutorial as Jupyter notebook | "More interactive for physicists" | Notebooks are not runnable in CI, go stale, and cannot be linted. The existing examples in `examples/` already serve as runable demos. | Write the tutorial as a structured Python module or RST/MD document. Reference the example files as "see also." |

---

## Feature Dependencies

```
[QuantumDot state macro registration]
    └──enables──> [SensorDot state macro registration (via MRO)]
    └──enables──> [QuantumDotPair state macro registration]
    └──enables──> [Test coverage for QD/SD/QDP defaults]

[XYDriveMacro delegation chain] (already complete)
    └──XMacro/YMacro──delegates──> [XYDriveMacro]
    └──X180Macro/X90Macro──delegates──> [XMacro/YMacro]

[OperationsRegistry] (already complete)
    └──initialize/measure/empty typed to QuantumComponent
    └──xy_drive/x/y/z typed to Qubit (LDQubit only)
    └──cnot/cz/swap/iswap typed to QubitPair (LDQubitPair only)

[Tutorial: Workflow 1 — use defaults]
    └──requires──> [QuantumDot/SensorDot/QuantumDotPair state macro registration]
    └──requires──> [LDQubit defaults already working]

[Tutorial: Workflow 2 — edit defaults (type level)]
    └──requires──> [component_types override schema documented]
    └──source material in──> [default_macro_overrides_example.py]

[Tutorial: Workflow 3 — per-component override (instance level)]
    └──requires──> [instances override schema documented]
    └──source material in──> [default_macro_overrides_example.py]

[Tutorial: Workflow 4 — external macro package]
    └──requires──> [@quam_dataclass constraint explained]
    └──requires──> [import path string format "module.path:Symbol" documented]
    └──escape hatch: component.macros["name"] = MyMacro() documented]
```

### Dependency Notes

- **QuantumDot registration enables SensorDot via MRO:** `SensorDot` inherits `QuantumDot`. `get_default_macro_factories()` walks the MRO in reverse (base to derived), so registering at `QuantumDot` automatically populates `SensorDot` unless a `SensorDot`-specific registration overrides. This means separate registration of `SensorDot` is only needed to override or extend, not to get inherited state macros. However, explicit separate registration is preferred for clarity and to allow future divergence.

- **XYDriveMacro → XMacro delegation requires xy_drive to be in macros:** `_AxisRotationMacro.apply()` calls `self.qubit.call_macro(SingleQubitMacroName.XY_DRIVE.value, ...)`. If `xy_drive` is absent, this raises `KeyError`. The catalog registration for `LDQubit` ensures `xy_drive` is always present. For `QuantumDot` (no XY channel), this macro must NOT be registered — which the proposed voltage-only macro set correctly omits.

- **OperationsRegistry role vs direct macro calls:** The `OperationsRegistry` provides a typed Python function interface on top of the macro dispatch. Both paths reach the same `component.macros[name].apply()`. The registry is useful for IDEs and static analysis but adds no runtime behavior. Tutorial must clarify this so customers do not believe one path is "correct."

- **Tutorial ordering:** Workflow 1 (use defaults) must appear before Workflow 2 (type overrides) which must appear before Workflow 3 (instance overrides). Workflow 4 (external package) is independent but builds conceptually on Workflow 2 and 3.

---

## MVP Definition

### Launch With (v1 of this milestone)

The minimum needed to close the `feature/qd_default_operations` milestone.

- [ ] `QuantumDot` registered in `component_macro_catalog.py` with `STATE_POINT_MACROS` — makes state macros available on all bare quantum dots
- [ ] `SensorDot` registered in `component_macro_catalog.py` with `STATE_POINT_MACROS` — ensures sensor dot get explicit (not just inherited) state macro defaults
- [ ] `QuantumDotPair` registered in `component_macro_catalog.py` with `STATE_POINT_MACROS` — closes the pair-level gap; no XY macros (voltage-only)
- [ ] Test: `QuantumDot`, `SensorDot`, `QuantumDotPair` each have `initialize`, `measure`, `empty` in `macros` after `wire_machine_macros(machine)` — prevents regression
- [ ] Test: XMacro/YMacro/ZMacro delegation chain reaches `xy_drive` and produces expected QUA output — validates the wrapper chain end-to-end (LDQubit only)
- [ ] Customer-facing tutorial covering all four workflows — without this, the system is not usable by new lab customers

### Add After Validation (v1.x)

Features to add once core is working and tested.

- [ ] `QuantumDotMacroName` StrEnum for voltage-only component macro names (analogous to `SingleQubitMacroName`) — reduces string literals; add only after the v1 patterns are stable to avoid premature abstraction
- [ ] TOML profile example file for lab use — once tutorials land, provide a `.toml` template showing `component_types.QuantumDot.macros.initialize` override syntax
- [ ] `OperationsRegistry` type annotation clarification — add `QuantumDot`/`SensorDot`/`QuantumDotPair` to `initialize`/`measure`/`empty` type hints in `default_operations.py` (currently typed to `QuantumComponent`, which is already correct but could be more specific)

### Future Consideration (v2+)

Features to defer until the pattern is established and customer feedback is available.

- [ ] `QuantumDot`-specific macro variants beyond state macros (e.g., charge-sensing, parity readout) — defer until user demand is clear; premature specialization creates maintenance burden
- [ ] Structured documentation beyond tutorial (API reference, migration guide from pre-macro code) — defer until the API stabilizes; v1 tutorial is enough to unblock customers

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| QuantumDot state macro registration | HIGH (unblocks all QD experiments) | LOW (3 lines in component_macro_catalog.py) | P1 |
| SensorDot state macro registration | HIGH (SensorDot is core to readout) | LOW (3 lines) | P1 |
| QuantumDotPair state macro registration | HIGH (pair-level experiments) | LOW (3 lines) | P1 |
| Test coverage for new registrations | HIGH (regression risk without it) | LOW (mirror existing patterns) | P1 |
| XY delegation chain verification tests | MEDIUM (chain already works; test confirms) | LOW (extend existing qubit macro tests) | P1 |
| Customer-facing tutorial (four workflows) | HIGH (discovery; without it the system is not usable) | MEDIUM (new documentation artifact, ~200 lines) | P1 |
| OperationsRegistry role clarification in tutorial | MEDIUM (reduces confusion) | LOW (add section to tutorial) | P1 |
| QuantumDotMacroName StrEnum | LOW (eliminates string literals) | LOW | P2 |
| TOML profile template | MEDIUM (lab adoption accelerator) | LOW | P2 |
| Specialized QD macros beyond state | LOW (no current demand) | HIGH (requires calibration logic) | P3 |

**Priority key:**
- P1: Must have for milestone close
- P2: Should have, add when time permits
- P3: Nice to have, future consideration

---

## Detailed Feature Notes

### (a) Default Macro Sets for Voltage-Only Components

**What voltage-only means:**

`QuantumDot`, `SensorDot`, and `QuantumDotPair` have `voltage_sequence` but no `xy` channel.
Their macro set should be strictly: `initialize`, `measure`, `empty` (the state-transition triad).

**What NOT to include:**

- `xy_drive`, `x`, `y`, `z`, `x180`...`z90`, `I` — these require an `xy` channel; including them causes `AttributeError` at apply time
- Two-qubit gate placeholders — `QuantumDotPair` has voltage-level pair operations but not gate-level operations; gate placeholders (`cnot`, `cz`, etc.) belong only to `LDQubitPair`

**Implementation path (confirmed by reading source):**

`STATE_POINT_MACROS` in `state_macros.py` already defines the correct factory dict:
```python
STATE_POINT_MACROS = {
    "initialize": InitializeStateMacro,
    "measure": MeasureStateMacro,
    "empty": EmptyStateMacro,
}
```
Adding three calls to `register_default_component_macro_factories()` in `component_macro_catalog.py` is the complete implementation. The macros themselves require no changes.

**Confidence:** HIGH — code path is clear, factory dict exists, registration pattern is established.

---

### (b) XMacro/YMacro/ZMacro Wrapper Chain Design

**Current state (already implemented):**

The chain is two-level:
1. `X180Macro` (fixed angle) → delegates to `XMacro` (canonical axis) via `_FixedAxisAngleMacro.apply()`
2. `XMacro` → delegates to `XYDriveMacro` via `_AxisRotationMacro.apply()`

**Why this design is correct for the override system:**

- Users who only want to change the drive physics replace `xy_drive`. All rotation wrappers update automatically.
- Users who want to change axis-specific behavior (e.g., add DRAG correction only to X) replace `x`. All fixed-angle X wrappers update automatically.
- Users who need a single fixed-angle variant (e.g., override only `x180` with a calibrated EV pulse) can replace at the leaf level.

**The key risk: broken chain on missing intermediate.**

If `x` is removed from a qubit's macros and a user calls `x180`, the `_FixedAxisAngleMacro` calls `self.qubit.call_macro("x", ...)` which raises `KeyError`. This is the correct behavior (fail loudly), but the tutorial must warn users: "Do not remove canonical `x`/`y`/`z` macros unless you also remove all fixed-angle wrappers that depend on them."

**What the tutorial must explain:**

- Diagram the two-level delegation chain
- Show the correct override at each level with minimal code
- Show the `KeyError` message that results from broken chain, so users can diagnose it

**Confidence:** HIGH — chain is fully implemented and tested for happy path; edge case (broken chain) is confirmed by reading `call_macro` in `MacroDispatchMixin`.

---

### (c) Customer Tutorial Structure for a 4-Workflow Override System

**What a good quickstart looks like for this system (derived from codebase analysis and established tutorial patterns):**

Physics library tutorials for plugin/override systems share a common structure observed across scientific Python libraries (QuTiP, Qiskit, PennyLane, JAX):

1. **Concept section** — explain what the system does and why (1 page max). Do not begin with code.
2. **Setup section** — show the minimal machine-build boilerplate once, reuse across all workflows.
3. **Workflow sections** — one section per workflow, increasing complexity order.
4. **Reference section** — macro name table, TOML schema summary.

**Table stakes for the tutorial:**

- Runnable code in every section (not pseudo-code)
- Each workflow section begins with "When to use this" (one sentence)
- No section assumes knowledge from the next section
- The TOML profile schema is shown before it is referenced in text

**Workflow 1 — Use defaults out of the box:**
Show: call `wire_machine_macros(machine)` with no arguments. Then call macros directly. Emphasize: state macros need voltage points defined beforehand (this is the most common beginner mistake).

**Workflow 2 — Edit defaults globally (component-type level):**
Show: `macro_overrides={"component_types": {"LDQubit": {"macros": {"initialize": {"factory": MyInit, "params": {...}}}}}}`. Emphasize: affects all instances of that type.

**Workflow 3 — Override per component (instance level):**
Show: `macro_overrides={"instances": {"qubits.q1": {"macros": {"x180": {"factory": TunedX180Macro}}}}}`. Emphasize: `instances` keys must match the exact component path from `_iter_macro_components`.

**Workflow 4 — Bring an external macro package:**
Show: TOML with `factory = "mylab.macros:LabSpecificX180"`. Emphasize: `@quam_dataclass` is required on custom classes for serialization. Show escape hatch: `component.macros["x180"] = MyMacro()` for one-off post-build overrides.

**Anti-pattern to include explicitly:** "Do not put non-`@quam_dataclass` macro classes in `component.macros` if you plan to save/load QuAM state."

**Confidence:** MEDIUM — structure derived from codebase patterns and established scientific Python documentation conventions. Actual tutorial content must be validated against customer feedback once shipped.

---

### (d) OperationsRegistry Role

**Current role (confirmed by reading `default_operations.py`):**

`OperationsRegistry` registers empty functions whose names match macro names. At runtime, `operations_registry.initialize(component)` dispatches to `component.macros["initialize"].apply()` via QuAM's registry mechanism. The function body is intentionally empty.

**What it provides:**

- Named, type-annotated entry points for IDE completion
- A discoverable list of all operations the system supports (import `operations_registry` → see all registered operations)
- Static-analysis surface: type hints on `component: Qubit` vs `component: QubitPair` allow mypy to flag wrong component types

**What it does NOT provide:**

- Any behavior not already in `component.macros`
- Validation that the macro exists (KeyError still propagates from macro dispatch)
- Any additional dispatch logic

**The consistent interaction with macro dispatch:**

Both paths reach the same code:
```
operations_registry.x180(qubit)   →  qubit.macros["x180"].apply()
qubit.x180()                       →  qubit.macros["x180"].apply()
```

**Recommendation for tutorial:** Explain the operations registry as "the typed function catalog" and direct dispatch via `qubit.macro_name()` as "the compact in-program syntax." Both are correct. Use the registry for QUA programs where type-checking is valuable. Use direct dispatch for inline experiments.

**Confidence:** HIGH — behavior confirmed by reading `default_operations.py` and `MacroDispatchMixin.__getattr__`.

---

## Sources

- Direct analysis of `/quam_builder/architecture/quantum_dots/operations/component_macro_catalog.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/operations/default_macros/single_qubit_macros.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/operations/default_macros/state_macros.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/operations/macro_registry.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/macro_engine/wiring.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/operations/default_operations.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/components/mixins/macro_dispatch.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/examples/default_macro_defaults_example.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/examples/default_macro_overrides_example.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/components/quantum_dot.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/components/sensor_dot.py`
- Direct analysis of `/quam_builder/architecture/quantum_dots/components/quantum_dot_pair.py`
- `.planning/PROJECT.md` — milestone requirements

---
*Feature research for: quam-builder QD Operations milestone (v1.0)*
*Researched: 2026-03-03*
