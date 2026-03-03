# Pitfalls Research

**Domain:** Registry-based macro system extension for quantum-dot hardware control (quam-builder)
**Researched:** 2026-03-03
**Confidence:** HIGH — all pitfalls derived directly from reading the existing source code, tests, and architecture documents

---

## Critical Pitfalls

### Pitfall 1: Using QubitMacro or QubitPairMacro as Base for QuantumDot/SensorDot/QuantumDotPair Macros

**What goes wrong:**

`QuantumDot`, `SensorDot`, and `QuantumDotPair` inherit `VoltageMacroMixin` but NOT `quam.components.Qubit` or `quam.components.QubitPair`. If a developer writes:

```python
class InitializeQDMacro(InitializeStateMacro, QubitMacro):  # WRONG
    ...
```

The `QubitMacro.qubit` property climbs the parent chain looking for a `Qubit` instance. On a `QuantumDot`, the parent chain never contains a `Qubit`, so the property raises `AttributeError: QubitOperation is not attached to a qubit`. The failure is silent at class definition time and only surfaces at runtime when `macro.qubit` is accessed.

The existing code already shows the correct pattern:

```python
class Initialize1QMacro(InitializeStateMacro, QubitMacro):  # for LDQubit (is-a Qubit)
class InitializeQDMacro(InitializeStateMacro):              # for QuantumDot (NOT a Qubit)
```

But the state macros in `state_macros.py` use `_owner_component()` instead of `self.qubit`, which is what makes them reusable. New QD-specific macros that accidentally inherit `QubitMacro` would lose that flexibility.

**Why it happens:**

The naming convention mirrors qubit behavior (`initialize`, `measure`, `empty`) and the import path `quam.components.macro.QubitMacro` is the first macro base class most developers encounter. The distinction between "a component that has qubit-like macros" and "a component that is a Qubit" is not enforced by the type system.

**How to avoid:**

- State macros for `QuantumDot`/`SensorDot`/`QuantumDotPair` must inherit directly from `QuamMacro` (or from shared bases like `InitializeStateMacro` which already does so), not from `QubitMacro`.
- Use `_owner_component(macro)` to resolve the parent component in `apply()` — the existing pattern in `state_macros.py` is the template.
- Add a type assertion test: verify that `QuantumDot` macro classes do NOT have `QubitMacro` in their MRO.

**Warning signs:**

- `AttributeError: QubitOperation is not attached to a qubit` at runtime when calling any macro on a `QuantumDot`.
- A new macro file imports `from quam.components.macro import QubitMacro` but the target component imports show `QuantumDot` or `SensorDot`.

**Phase to address:** Component catalog registration phase (Phase 1 of any QD-macro work). Include MRO verification in the test suite for every new macro class added for `QuantumDot`, `SensorDot`, and `QuantumDotPair`.

---

### Pitfall 2: Global `_REGISTERED` Flag Bleeds Across Tests

**What goes wrong:**

`component_macro_catalog.py` uses a module-level boolean:

```python
_REGISTERED = False

def register_default_component_macro_factories() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    ...
    _REGISTERED = True
```

Once the first test in a session imports any module that triggers `ensure_default_macros()`, `_REGISTERED` is permanently `True`. Any test that then:
- Calls `register_default_component_macro_factories()` with a modified or incomplete catalog
- Relies on re-running registration to pick up a new component type (e.g., `QuantumDot`)
- Mocks a registered component class to verify it appears in defaults

...will silently get the state from the first registration. There is no teardown hook to reset `_REGISTERED` between tests.

This means: if any existing test imports the catalog before the test that adds `QuantumDot` registration, the `QuantumDot`-only test sees the old (incomplete) catalog.

The internal registry `_COMPONENT_MACRO_FACTORIES` in `macro_registry.py` is also module-level and is never cleared.

**Why it happens:**

The idempotency guard was added to prevent duplicate registration in production use, which is correct. Tests were not written to account for cross-test contamination of module-level state.

**How to avoid:**

- Provide a `_reset_registration()` function in `component_macro_catalog.py` (private, for tests only) that sets `_REGISTERED = False` and clears `_COMPONENT_MACRO_FACTORIES`.
- Use a `pytest` fixture with `autouse=False` (or `scope="function"`) that calls the reset before tests that explicitly verify registration behavior.
- For new component tests, do NOT rely on module-level state being clean; always call `register_default_component_macro_factories()` inside a reset fixture.

**Warning signs:**

- A test for `QuantumDot` macros passes in isolation but fails when the full test suite runs.
- Adding a new component registration breaks an unrelated test that runs afterward.
- `QuantumDot` macros are missing from `component.macros` even though the registration call appears correct.

**Phase to address:** Every phase that adds component types to the catalog. The reset helper should be added before any new component type is registered.

---

### Pitfall 3: `_owner_component()` Parent-Climbing Breaks on Non-Standard Hierarchies

**What goes wrong:**

State macros call `_owner_component(self)` at runtime (inside `apply()` and `inferred_duration`):

```python
def _owner_component(macro: QuamMacro) -> Any:
    direct_parent = getattr(macro, "parent", None)
    if direct_parent is None:
        raise ValueError("Macro is not attached to a component.")

    if hasattr(direct_parent, "step_to_point") or hasattr(direct_parent, "call_macro"):
        return direct_parent

    owner = getattr(direct_parent, "parent", None)
    ...
```

This heuristic checks for `step_to_point` or `call_macro` on the parent. It assumes exactly one of two structures:

1. `component.macros["name"] = macro` — parent is the component itself
2. `component.macros["name"] = macro` where `macros` is a QuAM dict wrapper — parent is the dict wrapper, and `dict_wrapper.parent` is the component

For `QuantumDot` and `SensorDot`, the detection heuristic works if and only if those components have `step_to_point` (via `VoltageMacroMixin`) and/or `call_macro` (via `MacroDispatchMixin`). If a future refactor renames these methods, the detection silently falls back to climbing one more level — which may land on the wrong object (e.g., the `VirtualGateSet` or `QPU`).

For `QuantumDotPair`, which also has `VoltageMacroMixin`, the heuristic should work, but `QuantumDotPair.voltage_sequence` is `self.quantum_dots[0].voltage_sequence` — different from a direct-attach case. If the pair's macros try to resolve `owner.voltage_sequence.gate_set.macros[full_name]` via `_resolve_default_point_duration_ns`, the lookup will work only if a point with the full name exists.

**Why it happens:**

Duck-typing the parent chain is the only way to resolve the owner without requiring all components to inherit a common base. It is inherently fragile when method names change or when new intermediate wrappers appear.

**How to avoid:**

- Do not rename `step_to_point`, `call_macro`, or `_create_point_name` on any component that uses state macros — these are now implicit protocol methods.
- Add integration tests that call `macro.apply()` directly on `QuantumDot`-attached state macros (not just on `LDQubit`), verifying that `_owner_component` resolves correctly.
- Consider formalizing the protocol: add an `OwnedMacroComponent` ABC or Protocol class that declares `step_to_point`, `call_macro`, and `voltage_sequence`, so renames produce static type errors rather than silent runtime misbehavior.

**Warning signs:**

- `ValueError: Macro is not attached to a component` raised when calling a state macro on a `QuantumDot` that was built correctly.
- `inferred_duration` returns `None` unexpectedly — indicates `_resolve_default_point_duration_ns` is silently catching an `AttributeError`.
- Sticky-voltage tracking warning appears for a state macro that has `updates_voltage_tracking = True`.

**Phase to address:** Component registration phase. Add an integration fixture that instantiates a full `QuantumDot`-attached state macro and calls both `inferred_duration` and `apply()`.

---

### Pitfall 4: Delegation Chain Breaks When Intermediate Macro Is Missing From `self.macros`

**What goes wrong:**

The delegation chain is:

```
X90Macro.apply()  →  qubit.call_macro("x")
XMacro.apply()    →  qubit.call_macro("xy_drive")
XYDriveMacro.apply()  →  qubit.play_xy_pulse(...)
```

`_AxisRotationMacro._xy_drive_macro()` looks up `self.qubit.macros.get(SingleQubitMacroName.XY_DRIVE.value)`. If `xy_drive` is missing (e.g., because a component-type override accidentally removed it, or a custom macro profile disabled it), the result is:

```
KeyError: Missing canonical macro 'xy_drive' on qubit
```

Worse: `_FixedAxisAngleMacro.apply()` calls `self.qubit.call_macro(self.axis_macro_name, ...)`. If the canonical `x` macro is absent, this raises a `KeyError` that leaks `MacroDispatchMixin`'s internal error message about available macros. The chain has NO fallback — if any intermediate is missing, all fixed-angle macros silently fail to resolve.

For `QuantumDot`/`SensorDot`/`QuantumDotPair`, if only state macros are registered (the pattern to be added) and no XY macros are present, calling `qubit.x()` on a neighboring `LDQubit` that somehow shares a dispatch path will work fine — but calling it on a `QuantumDot` will fail with a confusing error about missing `xy_drive`, since `QuantumDot` has no XY channel at all.

**Why it happens:**

The delegation chain assumes a complete set of registered macros. There is no explicit validation that `xy_drive` exists before registering `x`/`y`/`x90`/etc. The `_REGISTERED` guard means that a partial registration from a test or misconfiguration is cached and never re-validated.

**How to avoid:**

- The `SINGLE_QUBIT_MACROS` dict in `single_qubit_macros.py` is the single source of truth for which macros must co-exist. If you add `XMacro`, you must also include `XYDriveMacro` in the same dict.
- Write a test that verifies the macro delegation chain for every registered component type: `X90Macro` resolves `x` which resolves `xy_drive` for `LDQubit`, and that none of these are present for `QuantumDot`.
- If `QuantumDot` eventually gains XY-type macros, they must be registered as a complete group — do not register `XMacro` without also registering `XYDriveMacro`.

**Warning signs:**

- `KeyError: Missing canonical macro 'xy_drive' on qubit` when a test creates a `QuantumDot` and calls an axis macro that should not exist on it.
- A component-type override profile disables `xy_drive` but leaves `x`/`y`/`x90` enabled — the TOML profile validator (if added) should reject this combination.

**Phase to address:** Single-qubit macro implementation phase and documentation phase. The tutorial must make the dependency order explicit.

---

### Pitfall 5: `OperationsRegistry` Type Annotations Diverge From Actual Macro Coverage

**What goes wrong:**

`default_operations.py` registers functions with `OperationsRegistry` using typed stubs:

```python
@operations_registry.register_operation
def x(component: Qubit, **kwargs):
    """Dispatch to component.macros['x']."""
```

The `component: Qubit` annotation signals that `x()` is only valid on `Qubit` instances. If `QuantumDot` gets XY macros registered but the `operations_registry` signature still reads `Qubit`, calling `operations_registry.x(quantum_dot)` may fail or be silently skipped at the `OperationsRegistry` dispatch layer — depending on how the registry performs type checking.

Conversely, `initialize`, `measure`, and `empty` are annotated as `QuantumComponent` (the common base). When `QuantumDot` gets state macros, these operations should work — but if the registry checks the annotation strictly, `QuantumDot`'s status (it inherits `VoltageMacroMixin` which inherits `QuantumComponent`) needs to be verified.

There is also no test that calls `operations_registry.initialize(quantum_dot_instance)` end-to-end — only tests for `LDQubit`.

**Why it happens:**

`OperationsRegistry` is a type-hinted facade: adding a new component type to the macro catalog does NOT automatically update the registry's annotations. The two systems are decoupled by design, but that decoupling creates a consistency gap that only fails at runtime if someone actually uses the registry with the new component type.

**How to avoid:**

- For each new component type added to the catalog, add an explicit test that calls every expected operation through `operations_registry.<name>(component_instance)`.
- If `QuantumDot` state macros are valid, confirm that `QuantumComponent` is the correct annotation for `initialize`/`measure`/`empty` (it currently is — do not tighten it to `Qubit`).
- Do not change existing `Qubit`-annotated operations (like `x`, `y`, `xy_drive`) to accept `QuantumDot` unless `QuantumDot` actually supports those operations.

**Warning signs:**

- `operations_registry.initialize(quantum_dot)` raises a type error or dispatches to the wrong macro.
- A test for `QuantumDot` state macros passes when calling `quantum_dot.initialize()` directly but fails when going through `operations_registry`.
- The `test_default_operations_match_canonical_enums` test (which verifies registry completeness against enum values) still passes even though new enums were added — because the enum was not updated alongside the registry.

**Phase to address:** Documentation and integration testing phase. The registry is the public API surface that customers use; integration tests through the registry should be added at the same time as the component catalog entries.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Registering `QuantumDot` with state macros only and documenting "XY macros are on LDQubit" | Ships the milestone faster | Customers who use `QuantumDot` directly instead of `LDQubit` hit silent no-ops or confusing `KeyError` | Acceptable if documentation is explicit and a `ValueError` is raised when XY macros are called on `QuantumDot` |
| Reusing `_owner_component()` heuristic for new component types without formalizing the protocol | No new abstractions required | A rename of `step_to_point` or `call_macro` silently breaks all state macros at runtime | Acceptable short-term; refactor to a typed Protocol within 1-2 milestones |
| Adding new enum members to `names.py` without adding matching entries to `SINGLE_QUBIT_MACRO_NAMES` tuple | Fast iteration | `test_default_operations_match_canonical_enums` fails; customers using the tuple for validation see incomplete lists | Never acceptable — always update the tuple when adding enum members |
| Writing documentation in module-by-module order (one page per `state_macros.py`, one per `single_qubit_macros.py`) | Easy to write | Customers cannot follow task-oriented flow ("how do I add a custom initialize?"); documentation gets skipped | Never acceptable for customer-facing tutorials |
| Using `replace=False` (merge, new keys win) as the default in `register_component_macro_factories` | Safe for incremental additions | A second call to register the same component type silently overrides only the specified keys; missing keys from the first call survive | Acceptable; document this behavior explicitly in the docstring |

---

## Integration Gotchas

| Integration Point | Common Mistake | Correct Approach |
|-------------------|----------------|------------------|
| QuAM serialization (`@quam_dataclass`) | Using a plain Python `dataclass` decorator instead of `@quam_dataclass` on a new macro class — the class is instantiated but cannot round-trip through `save()`/`load()` | Every concrete macro class that is stored in `component.macros` must use `@quam_dataclass`; check by calling `machine.save()` in a round-trip test |
| `wire_machine_macros` component path resolution | Using `"quantum_dots.dot0"` in `instances:` override when the component is stored under `"qubits.q1"` (LDQubit) or vice versa | The path format is `"<collection_name>.<component_id>"` where `collection_name` is one of the hardcoded names in `_iter_macro_components()` — adding `QuantumDot` requires adding `"quantum_dots"` to that tuple |
| TOML macro profile `factory` field | Providing a Python class object in TOML (not possible) vs. using the `"module.path:SymbolName"` string format | TOML profiles must always use string import paths; Python dict overrides can use class objects directly |
| `_iter_macro_components` in `wiring.py` | Adding a new collection to the machine (e.g., `sensor_dots`) without adding its name to `collection_names` in `_iter_macro_components` | Every collection whose components should receive macro overrides must be explicitly listed; the function is NOT auto-discovering |
| `MacroDispatchMixin.__getattr__` | A new attribute on a component that happens to match a macro name gets shadowed by the macro dispatch | Prefer named methods for new API surface; reserve dynamic attribute lookup (`__getattr__`) for macros only; use `component.call_macro("name")` in tests to avoid `__getattr__` ambiguity |
| `@quam_dataclass` on a mixin that also inherits `QuantumComponent` | Duplicate `@quam_dataclass` decorators in the MRO cause field registration to run multiple times | Apply `@quam_dataclass` at the leaf class level; mixins that are not meant to be instantiated directly should not carry the decorator |

---

## Performance Traps

Not a performance-sensitive domain (hardware control, not high-throughput software). The relevant "scale" question is the number of qubits/components in a single machine configuration.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `_rebuild_macro_dispatch()` called on every `__post_init__` | Each component instantiation rebuilds the compiled-dispatch cache; for 20+ qubits this is 20+ cache builds | Already acceptable at current scale; watch if machine sizes exceed ~100 components | Never in practice for quantum dot machines (typically 2-20 qubits) |
| `get_default_macro_factories` iterates the full MRO on every `ensure_default_macros()` call | Slow component initialization when MRO is deep (6+ levels for LDQubit) | Already cached at the dispatch layer; no action needed | Negligible for any realistic machine size |
| TOML profile loaded from disk on every `wire_machine_macros` call | If `wire_machine_macros` is called repeatedly in a notebook session, disk I/O is repeated | Cache the loaded profile at the call site; pass a pre-loaded dict instead of a file path for repeated calls | Not a problem in typical single-session lab use |

---

## "Looks Done But Isn't" Checklist

These are the most common false-completion states when extending the macro system.

- [ ] **QuantumDot catalog registration:** The registration call exists in `component_macro_catalog.py` AND the component is imported inside the function (lazy import, not at module level) AND `_REGISTERED` is reset in a test fixture for the new entry.
- [ ] **State macros for QuantumDot:** `_owner_component(self)` resolves to the `QuantumDot` (verify by calling `macro.apply()` in a test that asserts `step_to_point` was called on the correct instance, not on the machine or gate set).
- [ ] **SensorDot macros:** `SensorDot` inherits `QuantumDot`, so `get_default_macro_factories(sensor_dot)` resolves by MRO — it automatically inherits `QuantumDot` macros. Verify this inheritance works and does NOT double-register (i.e., that `SensorDot`-specific macros that differ from `QuantumDot` macros are in a separate registration call).
- [ ] **QuantumDotPair macros:** `QuantumDotPair` has `VoltageMacroMixin` but does NOT have `LDQubit`'s XY drive chain. Confirm that only state macros (initialize/measure/empty) and no axis-rotation macros appear in `QuantumDotPair.macros`.
- [ ] **`_iter_macro_components` coverage:** `wire_machine_macros` iterates components and applies overrides. If `"quantum_dots"` is not in `collection_names` inside `_iter_macro_components()`, no QD-specific instance override will ever apply — confirm by writing a test with `instances.quantum_dots.dot0` and verifying it is applied.
- [ ] **`OperationsRegistry` round-trip:** `operations_registry.initialize(quantum_dot)` executes the macro, not just calling `quantum_dot.initialize()` directly. These may diverge if the registry performs type-based dispatch filtering.
- [ ] **TOML profile round-trip:** A TOML profile that targets `QuantumDot` by type name (e.g., `[component_types.QuantumDot]`) applies correctly — confirm the type name string matches `type(component).__name__` exactly (it is case-sensitive).
- [ ] **Documentation tutorial:** A customer who reads only the tutorial (not the source code) can successfully add a custom `initialize` macro to a `QuantumDot` and save the result to disk. The tutorial must show the `wire_machine_macros` call, the TOML format, and a working `machine.save()` round-trip.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong base class (QubitMacro used for QuantumDot) | LOW | Change base class to `QuamMacro` or appropriate mixin; re-run tests to confirm parent resolution |
| `_REGISTERED` pollution causes test failures | LOW | Add `_reset_registration()` helper and use it in affected test fixtures; no production impact |
| `_owner_component()` resolves wrong parent | MEDIUM | Add `hasattr(parent, 'voltage_sequence')` as an additional check in `_owner_component()`; add integration test that catches the regression |
| Delegation chain missing intermediate macro | LOW | Add the missing macro to the factory dict and re-register; or update the TOML profile |
| `_iter_macro_components` misses new collection | LOW | Add collection name to the tuple; run `test_instance_override_path_supports_quam_mappings` equivalents for the new type |
| Documentation uses module-by-module structure customers skip | MEDIUM | Restructure documentation around the four customer workflows (use defaults / edit globally / override per instance / bring external package); existing content can be reorganized, not rewritten |
| `OperationsRegistry` annotation mismatch | LOW | Update the stub annotation for the affected function; write a regression test that calls the registry directly |
| QuAM round-trip fails because macro not using `@quam_dataclass` | MEDIUM | Add decorator; verify all field defaults are JSON-serializable; run `machine.save()` / `machine.load()` round-trip test |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Wrong base class for QD macros | Phase 1: Component catalog registration | MRO test: `assert QubitMacro not in QuantumDotStateMacro.__mro__` |
| `_REGISTERED` test isolation | Phase 1: Component catalog registration | All QD macro tests pass when run in isolation AND as part of the full suite |
| `_owner_component()` fragility | Phase 1: Component catalog registration | Integration test calls `macro.apply()` on QD-attached macros and asserts the correct component method was invoked |
| Delegation chain completeness | Phase 2: Single-qubit macro wrappers | Test that removing any link in the X90→X→XYDrive chain produces an explicit error, not a silent no-op |
| `OperationsRegistry` type drift | Phase 3: OperationsRegistry clarification | End-to-end test calls `operations_registry.<op>(quantum_dot)` for each state macro |
| `_iter_macro_components` missing collections | Phase 1 / macro wiring integration | Test with `instances.quantum_dots.*` override; confirm it applies and is visible in `component.macros` |
| Documentation customer workflow structure | Phase 4: Customer documentation | User-test checklist: a reader who starts from the tutorial (not the source) can complete all four customization workflows |
| QuAM serialization of new macros | Every phase that adds macro classes | `machine.save()` → `machine.load()` round-trip test for every new macro class |

---

## Sources

- `/Users/sebastian/Documents/GitHub/quam-builder/quam_builder/architecture/quantum_dots/operations/component_macro_catalog.py` — `_REGISTERED` flag and registration scope
- `/Users/sebastian/Documents/GitHub/quam-builder/quam_builder/architecture/quantum_dots/operations/macro_registry.py` — `_COMPONENT_MACRO_FACTORIES` module-level state, MRO resolution
- `/Users/sebastian/Documents/GitHub/quam-builder/quam_builder/architecture/quantum_dots/operations/default_macros/state_macros.py` — `_owner_component()` heuristic, `_iter_qpu_targets()`
- `/Users/sebastian/Documents/GitHub/quam-builder/quam_builder/architecture/quantum_dots/operations/default_macros/single_qubit_macros.py` — delegation chain structure (`_FixedAxisAngleMacro`, `_AxisRotationMacro`, `XYDriveMacro`)
- `/Users/sebastian/Documents/GitHub/quam-builder/quam_builder/architecture/quantum_dots/components/mixins/macro_dispatch.py` — `MacroDispatchMixin`, `__getattr__`, dispatch cache, parent-linking
- `/Users/sebastian/Documents/GitHub/quam-builder/quam_builder/architecture/quantum_dots/macro_engine/wiring.py` — `_iter_macro_components()` hardcoded collection list, `wire_machine_macros()` override application
- `/Users/sebastian/Documents/GitHub/quam-builder/quam_builder/architecture/quantum_dots/operations/default_operations.py` — `OperationsRegistry` stub annotations
- `/Users/sebastian/Documents/GitHub/quam-builder/.venv-gh/lib/python3.10/site-packages/quam/components/macro/qubit_macros.py` — `QubitMacro.qubit` property parent-climbing constraint
- `/Users/sebastian/Documents/GitHub/quam-builder/.venv-gh/lib/python3.10/site-packages/quam/components/macro/qubit_pair_macros.py` — `QubitPairMacro.qubit_pair` parent-climbing constraint
- `/Users/sebastian/Documents/GitHub/quam-builder/tests/builder/quantum_dots/test_macro_wiring.py` — existing wire override test patterns
- `/Users/sebastian/Documents/GitHub/quam-builder/tests/builder/quantum_dots/test_macro_names.py` — enum/registry consistency test structure

---
*Pitfalls research for: quam-builder QD macro system extension*
*Researched: 2026-03-03*
