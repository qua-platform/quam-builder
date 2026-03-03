# Phase 1: Catalog Registration - Research

**Researched:** 2026-03-03
**Domain:** Python macro registry — component catalog extension for quantum-dot architecture
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CAT-01 | `QuantumDot` registered in component catalog with state macros (`initialize`, `measure`, `empty`) | `STATE_POINT_MACROS` dict already exists in `state_macros.py`; one `register_component_macro_factories(QuantumDot, STATE_POINT_MACROS)` call in `component_macro_catalog.py` is sufficient |
| CAT-02 | `QuantumDotPair` registered in component catalog with state macros (`initialize`, `measure`, `empty`) | Same `STATE_POINT_MACROS` dict; one additional call for `QuantumDotPair`; do NOT include XY macros — voltage-only by design |
| CAT-03 | `SensorDot` registered with only `measure` macro; no `initialize` or `empty` | `SensorDot` inherits from `QuantumDot` — MRO resolution handles `initialize`/`measure`/`empty` via `QuantumDot` automatically UNLESS `SensorDot` is registered separately with a measure-only dict. Phase 1 must resolve which approach is used and document it. |
| TEST-04 | Pytest fixture resets `_REGISTERED` flag between test functions to prevent state leakage | `_reset_registration()` helper must be added to `component_macro_catalog.py` and `macro_registry.py`; fixture defined in `tests/conftest.py` or a new `tests/builder/quantum_dots/conftest.py` |
</phase_requirements>

## Summary

Phase 1 is the highest-leverage change in the v1.0 milestone. The entire macro system infrastructure is already in place — `MacroDispatchMixin`, `VoltageMacroMixin`, `register_component_macro_factories()`, `get_default_macro_factories()`, `STATE_POINT_MACROS`, `wire_machine_macros()` — and `_iter_macro_components()` in `wiring.py` already iterates `quantum_dots`, `sensor_dots`, and `quantum_dot_pairs`. The only gap is that `QuantumDot`, `QuantumDotPair`, and `SensorDot` have never been passed to `register_component_macro_factories()`. Fixing this requires three lines of code plus lazy imports in `component_macro_catalog.py`.

The non-trivial decision is the SensorDot approach. `SensorDot` inherits from `QuantumDot` (MRO order: `SensorDot → QuantumDot → VoltageMacroMixin → ...`). The `get_default_macro_factories()` function in `macro_registry.py` resolves factories by walking the MRO in reverse (base-to-derived), so registering `QuantumDot` with `STATE_POINT_MACROS` (initialize/measure/empty) would automatically give `SensorDot` all three state macros — which violates CAT-03 (SensorDot should have `measure` only, no `initialize` or `empty`). Therefore `SensorDot` must be registered **separately** with a measure-only dict that **overrides** (replaces) its inherited factories. `register_component_macro_factories()` supports this via the `replace=True` parameter.

The TEST-04 fixture is grouped with Phase 1 so it exists before any new catalog tests are written in Phase 2. The `_REGISTERED` flag in `component_macro_catalog.py` and the `_COMPONENT_MACRO_FACTORIES` dict in `macro_registry.py` are both module-level; without a reset mechanism, any test that runs after the first registration will see stale state.

**Primary recommendation:** Add three `register_component_macro_factories()` calls to `component_macro_catalog.py`, add `_reset_registration()` helpers to both `component_macro_catalog.py` and `macro_registry.py`, and define a `reset_catalog` pytest fixture in the test conftest.

---

## Standard Stack

### Core (No New Dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| quam | 0.5.0a2 | `QuamMacro`, `quam_dataclass`, `QuantumComponent` | Serialization contract for all macro classes; `@quam_dataclass` required on every concrete macro |
| qm-qua | 1.2.3.1 | QUA DSL used inside `macro.apply()` | `qua.program()` opens without a live server for testing |
| pytest | 8.4.2 / 9.0.1 | Test runner | Already in use |
| pytest-mock | 3.15.1 | `patch.object` on `voltage_sequence` methods | Established pattern for testing macro dispatch without hardware |

**No new runtime or dev dependencies are needed for Phase 1.**

### Existing Patterns Being Extended

| Symbol | Module | Purpose |
|--------|--------|---------|
| `register_component_macro_factories` | `operations/macro_registry.py` | The only function needed to close the gap |
| `STATE_POINT_MACROS` | `operations/default_macros/state_macros.py` | Already-defined dict: `{initialize: InitializeStateMacro, measure: MeasureStateMacro, empty: EmptyStateMacro}` |
| `_REGISTERED` | `operations/component_macro_catalog.py` | Module-level flag guarding idempotent registration |
| `_COMPONENT_MACRO_FACTORIES` | `operations/macro_registry.py` | Module-level dict keyed by fully-qualified class name |

---

## Architecture Patterns

### How the Catalog Registration System Works

```
wire_machine_macros(machine)
    └── register_default_component_macro_factories()   # component_macro_catalog.py
            └── register_component_macro_factories(ComponentType, macro_dict)
                    └── _COMPONENT_MACRO_FACTORIES[qualified_key] = macro_dict  # macro_registry.py

    └── for each component in machine:
            └── component.ensure_default_macros()      # MacroDispatchMixin
                    └── get_default_macro_factories(component)
                            └── walks MRO reversed (base→derived), merging _COMPONENT_MACRO_FACTORIES
                            └── returns merged MacroFactoryMap
                    └── for name, cls in factories.items():
                            └── if name not in self.macros: self.macros[name] = cls()
```

### Recommended File Change: `component_macro_catalog.py`

The entire fix is three registration calls added to `register_default_component_macro_factories()`:

```python
# Source: component_macro_catalog.py (existing pattern for LDQubit/LDQubitPair)
def register_default_component_macro_factories() -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    # Existing registrations (DO NOT CHANGE)
    from quam_builder.architecture.quantum_dots.components import QPU
    from quam_builder.architecture.quantum_dots.qubit import LDQubit
    from quam_builder.architecture.quantum_dots.qubit_pair import LDQubitPair

    register_component_macro_factories(QPU, QPU_STATE_MACROS)
    register_component_macro_factories(LDQubit, SINGLE_QUBIT_MACROS)
    register_component_macro_factories(LDQubitPair, TWO_QUBIT_MACROS)

    # NEW: Phase 1 additions (lazy imports inside function — same pattern as above)
    from quam_builder.architecture.quantum_dots.components.quantum_dot import QuantumDot
    from quam_builder.architecture.quantum_dots.components.quantum_dot_pair import QuantumDotPair
    from quam_builder.architecture.quantum_dots.components.sensor_dot import SensorDot

    register_component_macro_factories(QuantumDot, STATE_POINT_MACROS)
    register_component_macro_factories(QuantumDotPair, STATE_POINT_MACROS)
    # SensorDot: replace=True so its MRO-inherited QuantumDot factories are overridden
    # with measure-only. This enforces CAT-03 (no initialize/empty on SensorDot).
    register_component_macro_factories(
        SensorDot,
        {VoltagePointName.MEASURE.value: SensorDotMeasureMacro},
        replace=True,
    )

    _REGISTERED = True
```

**Note on `SensorDotMeasureMacro`:** The existing `MeasureStateMacro` in `state_macros.py` delegates to `owner.step_to_point()`. `SensorDot` has `step_to_point` via `VoltageMacroMixin`, but the semantically correct measure path for a sensor dot goes through `readout_resonator.measure()`, not through a voltage step. See the Critical Decision below.

### Critical Decision: SensorDot `measure` macro implementation

**What the requirements say:** CAT-03 specifies that `SensorDot` gets a `measure` macro dispatching via the readout resonator. But `MeasureStateMacro.apply()` calls `owner.step_to_point()` — it steps the voltage gate, not the readout resonator.

**Two valid designs:**

Option A — `MeasureStateMacro` reused for voltage step only:
- Register `SensorDot` with `{measure: MeasureStateMacro, replace=True}` (no initialize/empty)
- Keeps consistency with how `QuantumDot` measures (voltage step to measure point)
- Does NOT call `readout_resonator.measure()` — this is only the preparation step

Option B — New `SensorDotMeasureMacro` that dispatches via readout resonator:
- Register `SensorDot` with a new `SensorDotMeasureMacro` that calls `owner.readout_resonator.measure()`
- Matches requirement language "dispatching via the readout resonator"
- Requires a new macro class in `state_macros.py` or a new `sensor_dot_macros.py` file

**Recommendation:** The requirement text says "dispatching via the readout resonator" which implies Option B. However, the existing `SensorDot.measure()` method already calls `self.readout_resonator.measure(*args, **kwargs)`. The new `SensorDotMeasureMacro` should wrap that call. The macro class is short — it belongs in `state_macros.py` alongside the other state macros (or in a new `sensor_dot_macros.py` for cleaner separation).

**The planner must decide**: whether to create `SensorDotMeasureMacro` calling `owner.readout_resonator.measure()`, or to reuse `MeasureStateMacro` for voltage-step-only behavior. This decision is architectural and has testing implications (what does the test assert the macro does?). **Document the chosen design explicitly in the plan.**

### Reset Helpers for Test Isolation (TEST-04)

```python
# To add to component_macro_catalog.py
def _reset_registration() -> None:
    """Reset global registration state. FOR TESTING ONLY.

    Called by the catalog_reset pytest fixture to ensure each test that
    explicitly verifies registration behavior starts from a clean slate.
    """
    global _REGISTERED
    _REGISTERED = False
```

```python
# To add to macro_registry.py
def _reset_registry() -> None:
    """Clear all registered macro factories. FOR TESTING ONLY."""
    _COMPONENT_MACRO_FACTORIES.clear()
```

```python
# Fixture — where to put it: tests/conftest.py (root-level conftest)
# or a new tests/architecture/quantum_dots/operations/conftest.py

import pytest
from quam_builder.architecture.quantum_dots.operations import component_macro_catalog
from quam_builder.architecture.quantum_dots.operations import macro_registry

@pytest.fixture
def reset_catalog():
    """Reset catalog and registry before each test that uses it.

    Use this fixture in any test that directly verifies registration behavior.
    Do NOT use autouse=True — only tests that care about registration state
    should pull this in explicitly.
    """
    component_macro_catalog._reset_registration()
    macro_registry._reset_registry()
    yield
    # No teardown needed — next test using this fixture resets again
```

### Anti-Patterns to Avoid

- **Do not** place `reset_catalog` as `autouse=True` in any conftest — it breaks tests that rely on registration being complete from `ensure_default_macros()` during component construction.
- **Do not** register `QuantumDot` with XY macros (`XYDriveMacro`, `XMacro`, etc.) — `QuantumDot` has no `xy` drive; these macros call `self.qubit.xy` and will raise `AttributeError`.
- **Do not** inherit from `QubitMacro` for any macro class targeting `QuantumDot`, `SensorDot`, or `QuantumDotPair` — the `QubitMacro.qubit` property climbs the parent chain looking for a `Qubit` instance and raises `AttributeError` on voltage-only components.
- **Do not** import `QuantumDot`, `SensorDot`, or `QuantumDotPair` at module level in `component_macro_catalog.py` — use lazy imports inside the function (same pattern as existing `LDQubit` import) to avoid import-cycle side effects.
- **Do not** register `QuantumDotPair` with two-qubit gate macros (CNOT/CZ/SWAP/iSWAP) — those belong to `LDQubitPair` which has XY-drive semantics.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MRO-aware factory resolution | Custom class-hierarchy walker | `get_default_macro_factories()` in `macro_registry.py` | Already implemented; walks MRO in `reversed(type(component).mro())` order |
| Idempotent catalog registration | Custom deduplication logic | `register_component_macro_factories(..., replace=False)` (default) | Merge-with-new-keys-win already implemented |
| State macro parent resolution | `self.parent` direct access | `_owner_component(macro)` in `state_macros.py` | Handles both direct-parent and QuAM-dict-wrapper-parent layouts |
| Component path iteration | Manual `getattr` loops | `_iter_macro_components(machine)` in `wiring.py` | Already hardcodes `quantum_dots`, `sensor_dots`, `quantum_dot_pairs` |
| Test machine construction | New fixture code | Reuse `qd_machine` fixture from `tests/architecture/quantum_dots/conftest.py` | Full 4-dot, 2-pair, 1-sensor machine; cover the catalog tests with this |

**Key insight:** Every supporting piece is already built and tested. Phase 1 is three registration calls plus two helper functions and one fixture. Do not redesign any layer.

---

## Common Pitfalls

### Pitfall 1: Wrong Base Class for QD Macros
**What goes wrong:** Using `QubitMacro` (from `quam.components.macro`) as a base for any macro targeting `QuantumDot`/`SensorDot`/`QuantumDotPair`. `QubitMacro.qubit` climbs the parent chain for a `Qubit` instance; voltage-only components are not `Qubit` instances.
**Why it happens:** `QubitMacro` is the first macro base class most developers encounter, and the macro names (`initialize`, `measure`) look qubit-like.
**How to avoid:** Use `QuamMacro` as base. Use `_owner_component(self)` to resolve parent in `apply()`. `state_macros.py` already demonstrates the correct pattern.
**Warning signs:** `AttributeError: QubitOperation is not attached to a qubit` at runtime.

### Pitfall 2: `_REGISTERED` Flag Bleeds Across Tests
**What goes wrong:** Once any test causes `ensure_default_macros()` to be called, `_REGISTERED` is permanently `True` for the test session. Tests that add new component registrations and then check if they appear find stale state.
**Why it happens:** The idempotency guard was designed for production, not for test isolation.
**How to avoid:** Add `_reset_registration()` + `_reset_registry()` helpers; use `reset_catalog` fixture in tests that verify registration behavior. TEST-04 exists precisely to prevent this.
**Warning signs:** Test passes when run in isolation (`pytest tests/path/test.py`) but fails in full suite (`make test`).

### Pitfall 3: SensorDot Inherits Unwanted Macros via MRO
**What goes wrong:** If only `QuantumDot` is registered with `STATE_POINT_MACROS` (initialize/measure/empty), then `SensorDot` (which inherits from `QuantumDot`) also receives `initialize` and `empty` via MRO resolution — violating CAT-03.
**Why it happens:** MRO-aware resolution merges registrations from all ancestor classes. `QuantumDot` registration flows down to `SensorDot`.
**How to avoid:** Register `SensorDot` explicitly with `replace=True` and a measure-only factory dict. This overrides the inherited factories for `SensorDot` specifically.
**Warning signs:** `assert "initialize" not in sensor_dot.macros` fails after `wire_machine_macros()`.

### Pitfall 4: `_iter_macro_components` Already Correct — Don't Change It
**What goes wrong:** Developer re-reads `_iter_macro_components` and thinks it needs updating because QD types appear there but are not registered.
**Why it happens:** The collection names (`quantum_dots`, `sensor_dots`, `quantum_dot_pairs`) are already in `_iter_macro_components()`. The function is correct; only the catalog was missing entries.
**How to avoid:** Confirm the collection names are already present. No change to `wiring.py` is needed.

### Pitfall 5: `_owner_component()` Parent-Climbing Works for QuantumDot
**What works:** `_owner_component(macro)` checks for `step_to_point` or `call_macro` on the parent. Both `QuantumDot` and `QuantumDotPair` have these methods via `VoltageMacroMixin`. Resolution works correctly.
**What must not be renamed:** `step_to_point` and `call_macro` are implicit protocol methods for the heuristic. Renaming either silently breaks all state macros.

---

## Code Examples

### Pattern 1: Existing Registration (Template to Follow)
```python
# Source: component_macro_catalog.py (existing)
from quam_builder.architecture.quantum_dots.qubit import LDQubit

register_component_macro_factories(LDQubit, SINGLE_QUBIT_MACROS)
# SINGLE_QUBIT_MACROS includes initialize/measure/empty PLUS xy macros
# Do NOT use this dict for QuantumDot — use STATE_POINT_MACROS only
```

### Pattern 2: State Macros Dict (Already Defined — Use Directly)
```python
# Source: state_macros.py
STATE_POINT_MACROS = {
    VoltagePointName.INITIALIZE.value: InitializeStateMacro,   # "initialize"
    VoltagePointName.MEASURE.value: MeasureStateMacro,         # "measure"
    VoltagePointName.EMPTY.value: EmptyStateMacro,             # "empty"
}
```

### Pattern 3: MRO-Aware Factory Resolution (How SensorDot inherits)
```python
# Source: macro_registry.py
def get_default_macro_factories(component: object) -> MacroFactoryMap:
    resolved: MacroFactoryMap = dict(UTILITY_MACRO_FACTORIES)  # align, wait
    for component_type in reversed(type(component).mro()):
        key = _component_key(component_type)
        if key in _COMPONENT_MACRO_FACTORIES:
            resolved.update(_COMPONENT_MACRO_FACTORIES[key])
    # Later entries (more-derived) WIN over earlier entries (more-base)
    return resolved
```

### Pattern 4: Macro dispatch test (how to test that macros are present)
```python
# Source: test_macro_wiring.py (established pattern)
from quam_builder.architecture.quantum_dots.macro_engine import wire_machine_macros

def test_quantum_dot_has_state_macros(qd_machine, reset_catalog):
    wire_machine_macros(qd_machine)
    for qd in qd_machine.quantum_dots.values():
        assert "initialize" in qd.macros
        assert "measure" in qd.macros
        assert "empty" in qd.macros
```

### Pattern 5: Verifying SensorDot measure-only (test template)
```python
def test_sensor_dot_has_measure_only(qd_machine, reset_catalog):
    wire_machine_macros(qd_machine)
    for sd in qd_machine.sensor_dots.values():
        assert "measure" in sd.macros
        assert "initialize" not in sd.macros
        assert "empty" not in sd.macros
```

### Pattern 6: SensorDotMeasureMacro skeleton (if implementing Option B)
```python
# New class in state_macros.py (or sensor_dot_macros.py)
# Source: state_macros.py pattern, adapted for readout resonator dispatch
@quam_dataclass
class SensorDotMeasureMacro(QuamMacro):
    """Dispatch measure to SensorDot readout resonator."""

    def apply(self, *args, **kwargs):
        owner = _owner_component(self)
        owner.readout_resonator.measure(*args, **kwargs)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Macros defined on component classes directly | Catalog registration decoupled from component classes | Current branch | Enables external package overrides without forking |
| Idempotent registration only in production | Needs `_reset_registration()` for test isolation | Phase 1 (new) | Prevents TEST-04 cross-test contamination |
| MRO resolution handles SensorDot implicitly | SensorDot registered explicitly with `replace=True` | Phase 1 (new) | Enforces measure-only constraint from CAT-03 |

**Deprecated/outdated:**
- The `SensorDot.measure()` and `QuantumDotPair.measure()` methods defined directly on the component classes: these are overriding each other in unexpected ways. The new system routes measure via the macro catalog. The existing methods should remain (they are called by the macro), but the macro is the new canonical entry point.

---

## Open Questions

1. **SensorDot macro implementation: voltage step vs readout resonator dispatch**
   - What we know: CAT-03 says "dispatching via the readout resonator"; `SensorDot.measure()` already calls `readout_resonator.measure()`; `MeasureStateMacro.apply()` calls `step_to_point()` (voltage gate, not resonator)
   - What's unclear: Whether "dispatching via the readout resonator" means the macro wraps `readout_resonator.measure()` (Option B), or whether the macro steps to a measure voltage point and the resonator call is the user's responsibility (Option A)
   - Recommendation: Implement Option B (`SensorDotMeasureMacro` calling `owner.readout_resonator.measure()`). This matches the literal requirement and is what a customer expects when calling `sensor_dot.measure()`. The macro is short and reuses the `_owner_component()` pattern.

2. **Where to define `reset_catalog` fixture**
   - What we know: Root `conftest.py` is nearly empty; `tests/architecture/quantum_dots/conftest.py` exists (defines `qd_machine`); `tests/conftest.py` handles server marking only
   - What's unclear: Whether `reset_catalog` belongs in `tests/conftest.py` (global) or a sub-conftest closer to the catalog tests
   - Recommendation: Put it in `tests/conftest.py` so it is discoverable by any test file that needs it, with `autouse=False` so it only activates where explicitly requested.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 / 9.0.1 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/architecture/quantum_dots/components/ tests/builder/quantum_dots/test_macro_wiring.py -x -q` |
| Full suite command | `pytest tests/ -m "not server" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAT-01 | `QuantumDot.macros` contains `initialize`, `measure`, `empty` after `wire_machine_macros()` | unit | `pytest tests/architecture/quantum_dots/components/test_quantum_dot.py -x -q` | ✅ (file exists, needs new test class) |
| CAT-02 | `QuantumDotPair.macros` contains `initialize`, `measure`, `empty` after `wire_machine_macros()` | unit | `pytest tests/architecture/quantum_dots/components/test_quantum_dot_pair.py -x -q` | ✅ (file exists, needs new test class) |
| CAT-03 | `SensorDot.macros` contains `measure` only; `initialize` and `empty` are absent | unit | `pytest tests/architecture/quantum_dots/components/test_sensor_dot.py -x -q` | ✅ (file exists, needs new test class) |
| TEST-04 | Catalog `_REGISTERED` flag is reset between test functions | fixture | `pytest tests/ -m "not server" -q` (regression: verify full suite passes) | ❌ Wave 0 — fixture must be created |

### Sampling Rate
- **Per task commit:** `pytest tests/architecture/quantum_dots/components/ tests/builder/quantum_dots/test_macro_wiring.py -x -q`
- **Per wave merge:** `pytest tests/ -m "not server" -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` — add `reset_catalog` fixture (calls `_reset_registration()` + `_reset_registry()`); covers TEST-04
- [ ] `quam_builder/architecture/quantum_dots/operations/component_macro_catalog.py` — add `_reset_registration()` helper function
- [ ] `quam_builder/architecture/quantum_dots/operations/macro_registry.py` — add `_reset_registry()` helper function

*(The test files for CAT-01/02/03 exist but currently lack catalog-registration test classes. These are created in Wave 1, not Wave 0, since they depend on the production code change.)*

---

## Sources

### Primary (HIGH confidence — direct source code inspection)
- `quam_builder/architecture/quantum_dots/operations/component_macro_catalog.py` — existing registration pattern, `_REGISTERED` flag, lazy import convention
- `quam_builder/architecture/quantum_dots/operations/macro_registry.py` — `register_component_macro_factories()`, `get_default_macro_factories()`, MRO resolution, `_COMPONENT_MACRO_FACTORIES` module-level state
- `quam_builder/architecture/quantum_dots/operations/default_macros/state_macros.py` — `STATE_POINT_MACROS` dict, `InitializeStateMacro`/`MeasureStateMacro`/`EmptyStateMacro`, `_owner_component()` heuristic
- `quam_builder/architecture/quantum_dots/macro_engine/wiring.py` — `wire_machine_macros()`, `_iter_macro_components()` collection names confirmed to include `quantum_dots`/`sensor_dots`/`quantum_dot_pairs`
- `quam_builder/architecture/quantum_dots/components/quantum_dot.py` — `QuantumDot` class; no XY drive; voltage-only; `VoltageMacroMixin` inheritance
- `quam_builder/architecture/quantum_dots/components/sensor_dot.py` — `SensorDot(QuantumDot)` inheritance; `readout_resonator.measure()` delegation
- `quam_builder/architecture/quantum_dots/components/quantum_dot_pair.py` — `QuantumDotPair(VoltageMacroMixin)` without qubit semantics
- `quam_builder/architecture/quantum_dots/components/mixins/macro_dispatch.py` — `MacroDispatchMixin`, `ensure_default_macros()`, `_rebuild_macro_dispatch()`
- `tests/builder/quantum_dots/test_macro_wiring.py` — established mock and dispatch test patterns
- `tests/architecture/quantum_dots/conftest.py` — `qd_machine` fixture (full LossDiVincenzoQuam with 4 dots, 2 pairs, 1 sensor)
- `tests/macros/conftest.py` — `machine` fixture with same topology (different fixture name)
- `tests/conftest.py` — root conftest (currently handles only server marker; reset fixture goes here)
- `.planning/research/SUMMARY.md`, `STACK.md`, `PITFALLS.md` — prior project-level research

### Secondary (MEDIUM confidence — inferred from patterns)
- MRO-override behavior: inferred from reading `get_default_macro_factories()` source and Python MRO spec; HIGH confidence on the MRO traversal order, MEDIUM on the `replace=True` as the correct override mechanism (verified by reading `register_component_macro_factories()` source)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all locked versions confirmed from `uv.lock`; no new deps needed
- Architecture (registration gap, fix approach): HIGH — confirmed by reading source; three registration calls are the complete fix
- SensorDot approach (measure-only via MRO override): HIGH on mechanism; MEDIUM on which macro implementation to use (Option A vs B — planner must decide)
- Test isolation (`_REGISTERED` / `_COMPONENT_MACRO_FACTORIES`): HIGH — both module-level state locations confirmed; reset helper pattern clear
- `_iter_macro_components` coverage: HIGH — confirmed `quantum_dots`, `sensor_dots`, `quantum_dot_pairs` are already in the collection names tuple

**Research date:** 2026-03-03
**Valid until:** 2026-04-02 (30 days — quam 0.5.0a2 is pre-release; re-verify if version changes)
