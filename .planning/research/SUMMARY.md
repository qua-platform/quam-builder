# Project Research Summary

**Project:** quam-builder — QD Operations Milestone (feature/qd_default_operations)
**Domain:** Python physics-hardware library — macro dispatch system extension for quantum dot components
**Researched:** 2026-03-03
**Confidence:** HIGH

## Executive Summary

This is a subsequent milestone on an in-progress branch, not a greenfield project. The quam-builder macro system is a layered, config-driven architecture that wires named QUA behaviors (macros) onto quantum hardware components at runtime through `wire_machine_macros()`. The system is almost complete: `QPU`, `LDQubit`, and `LDQubitPair` are fully registered in the component catalog with their default macro sets, and all single-qubit wrapper classes (`XMacro`, `YMacro`, `ZMacro`, `X180Macro`, etc.) are implemented. The gap is narrow and precise: `QuantumDot`, `SensorDot`, and `QuantumDotPair` inherit all the dispatch infrastructure via `VoltageMacroMixin` but are absent from the catalog, so they receive only utility macros (`align`, `wait`) after `wire_machine_macros()`.

The recommended approach is incremental and surgical. Three `register_component_macro_factories()` calls in `component_macro_catalog.py` — one each for `QuantumDot`, `SensorDot` (optional, MRO covers it), and `QuantumDotPair` — together with `STATE_POINT_MACROS` (already defined in `state_macros.py`) complete the core feature gap. The test suite must be extended to assert that `initialize`, `measure`, and `empty` appear in `macros` for all three component types after wiring. The final deliverable is a customer-facing tutorial covering the four macro customization workflows, without which the system is not discoverable by new lab users.

The key risks are: (1) accidentally using `QubitMacro` as a base class for voltage-only component macros, which fails silently at class-definition time but raises `AttributeError` at macro application time; (2) module-level `_REGISTERED` flag bleed across tests, which causes QD-specific registration tests to see stale state from earlier test runs; and (3) breaking the XY delegation chain by registering incomplete macro sets. All three are well-understood and have concrete prevention patterns confirmed in the existing codebase.

## Key Findings

### Recommended Stack

No new runtime dependencies are needed. The existing stack — quam 0.5.0a2, qm-qua 1.2.3.1, pytest, pytest-mock, ruff, mypy — is sufficient for all three deliverables. The only optional addition is `nbmake` (dev-only) if tutorials are delivered as Jupyter notebooks rather than structured Python scripts. The FEATURES.md analysis actually flags notebook tutorials as an anti-feature for this milestone (not runnable in CI, go stale), recommending instead a structured Python module or Markdown document with references to the existing `examples/` scripts.

**Core technologies:**
- `quam 0.5.0a2`: `QuamMacro`, `quam_dataclass`, `QuantumComponent` base classes — the serialization contract for all new macro classes
- `qm-qua 1.2.3.1`: QUA DSL used inside `macro.apply()` implementations; `qua.program()` context opens without a live server for unit testing
- `pytest + pytest-mock`: `patch.object` on `voltage_sequence` methods or `call_macro` is the established testing pattern; no new tools required
- Python stdlib `tomllib`: already used in `macro_engine/wiring.py` for TOML profile loading; no third-party TOML lib needed

### Expected Features

**Must have (table stakes):**
- `QuantumDot` registered with state macros (`initialize`, `measure`, `empty`) — blocks all QD experiments; three-line fix in `component_macro_catalog.py`
- `SensorDot` registered (or inherits via MRO from `QuantumDot`) — sensor dot is the core readout path
- `QuantumDotPair` registered with state macros only (no XY macros — voltage-only by design)
- Test coverage for all three component types asserting macro presence after wiring — regression prevention
- XY delegation chain verification tests (`X90 → X → XYDrive` for `LDQubit`; absence of XY macros confirmed for `QuantumDot`)
- Customer-facing tutorial covering all four override workflows — without this, the system is not usable by new lab customers

**Should have (competitive):**
- `QuantumDotMacroName` StrEnum for voltage-only macro names (reduces string literals; add once v1 patterns stabilize)
- TOML profile template file for labs to commit calibrated macro parameters
- `OperationsRegistry` type annotation clarification for `QuantumDot`/`SensorDot`/`QuantumDotPair`

**Defer (v2+):**
- `QuantumDot`-specific macro variants beyond state macros (charge-sensing, parity readout) — wait for user demand
- Full hosted API documentation (Sphinx/RST) — tutorial plus README is sufficient for this milestone
- Two-qubit gate macros for `QuantumDotPair` (CNOT/CZ/SWAP) — voltage-only pairs do not have gate semantics

### Architecture Approach

The macro system is a four-layer stack: (1) Customer/Experiment Layer — `wire_machine_macros()` and component method dispatch; (2) Macro Engine — TOML profile loading, deep-merge of overrides, and iteration over all components; (3) Registry/Catalog — MRO-aware factory resolution keyed by fully-qualified class name; (4) Macro Class Layer — concrete `@quam_dataclass` implementations organized by component type. The entire system is config-driven and serializable: macro objects stored in `component.macros` survive QuAM save/load cycles because all classes use `@quam_dataclass`. The gap is entirely in layer (3) — the catalog — not in any of the surrounding layers.

**Major components:**
1. `component_macro_catalog.py` — one-time idempotent registration mapping component types to default macro factory dicts; the single file change that closes the gap
2. `macro_registry.py` — module-level dict keyed by fully-qualified class name; MRO-aware resolution that makes `SensorDot` inherit `QuantumDot` registrations automatically
3. `state_macros.py` — `InitializeStateMacro`, `MeasureStateMacro`, `EmptyStateMacro`; uses `_owner_component()` heuristic instead of `self.qubit`, making them reusable for both voltage-only and qubit component types
4. `MacroDispatchMixin` — `macros` dict, `__getattr__` dispatch, compiled-callable cache, sticky-voltage tracking; requires no changes
5. `wire_machine_macros` — already iterates `quantum_dots`, `sensor_dots`, `quantum_dot_pairs`; registration fills it in automatically

### Critical Pitfalls

1. **Wrong base class (`QubitMacro`) for `QuantumDot` macros** — `QubitMacro.qubit` climbs the parent chain for a `Qubit` instance; `QuantumDot` is not a `Qubit`, so it raises `AttributeError` at runtime. Use `QuamMacro` as base and resolve owner via `_owner_component()`. Add MRO assertion tests: `assert QubitMacro not in QuantumDotStateMacro.__mro__`.

2. **`_REGISTERED` flag bleed across tests** — `component_macro_catalog.py` uses a module-level boolean guard that is never reset between test runs. QD-specific registration tests pass in isolation but fail in the full suite. Add a private `_reset_registration()` helper and use it in a `scope="function"` pytest fixture for all new component catalog tests.

3. **`_owner_component()` parent-climbing fragility** — The state macro parent-resolution heuristic checks for `step_to_point` or `call_macro` on the parent. Renaming these methods silently breaks all state macros. Add integration tests that call `macro.apply()` on `QuantumDot`-attached macros and assert the correct component method was invoked; do not rename these interface methods without updating the heuristic.

4. **Delegation chain completeness** — `X90Macro` → `XMacro` → `XYDriveMacro` fails with `KeyError` if any intermediate is missing. Never register `XMacro` without also registering `XYDriveMacro`. Confirm that `QuantumDot` has none of these (correct) and that `LDQubit` has all of them (complete set).

5. **`OperationsRegistry` annotation drift** — Adding `QuantumDot` to the catalog does not automatically update `default_operations.py` annotations. Confirm `initialize`/`measure`/`empty` are typed to `QuantumComponent` (they are — do not tighten to `Qubit`). Write end-to-end tests that call `operations_registry.initialize(quantum_dot_instance)` to catch dispatch mismatches.

## Implications for Roadmap

Based on combined research, this milestone maps cleanly to four sequential phases. The first phase is the highest-leverage change (fewest lines, most unblocked downstream work). Each subsequent phase builds on confirmation that the previous phase works correctly.

### Phase 1: Component Catalog Registration

**Rationale:** This is the single highest-leverage change in the milestone. The catalog gap is the root cause of all functional failures for `QuantumDot`, `SensorDot`, and `QuantumDotPair`. Fixing it unblocks QPU dispatch (`QPUInitializeMacro._iter_qpu_targets` falls back to `machine.quantum_dots` and currently raises `KeyError`), enables QD/QDP defaults for all experiments, and is a prerequisite for all downstream testing and documentation.
**Delivers:** `QuantumDot`, `SensorDot`, `QuantumDotPair` each have `initialize`, `measure`, `empty` in `macros` after `wire_machine_macros(machine)`.
**Addresses:** All three P1 table-stakes features (QD, SD, QDP state macro registration).
**Files changed:** `operations/component_macro_catalog.py` (three lines + lazy imports).
**Avoids:** Pitfall 2 (`_REGISTERED` bleed) — add `_reset_registration()` helper in this phase before any new tests that verify registration.

### Phase 2: Test Coverage for New Component Registrations

**Rationale:** Catalog registration without tests is a regression risk. The existing test patterns in `test_macro_wiring.py` and `test_macro_classes.py` are the templates — this phase mirrors them for QD/SD/QDP. It also confirms the MRO-based SensorDot inheritance works correctly and that the `_owner_component()` heuristic resolves to the right component.
**Delivers:** Assertion coverage that `initialize`, `measure`, `empty` are present on all three new component types after wiring; integration tests calling `macro.apply()` on QD-attached macros; component-type and instance-level override tests for `QuantumDot`.
**Files changed:** `tests/architecture/quantum_dots/components/test_quantum_dot.py`, `test_sensor_dot.py`, `test_quantum_dot_pair.py`; `tests/builder/quantum_dots/test_macro_wiring.py`.
**Avoids:** Pitfall 1 (wrong base class — caught by MRO assertion tests), Pitfall 3 (`_owner_component()` fragility — caught by `apply()` integration tests), Pitfall 5 (OperationsRegistry drift — add `operations_registry.initialize(quantum_dot)` round-trip tests here).

### Phase 3: Single-Qubit Macro Wrapper Validation and OperationsRegistry Clarification

**Rationale:** The XY wrapper chain (`X90 → X → XYDrive`) is reported as already implemented in `single_qubit_macros.py`, but the milestone requirement includes confirming completeness. This phase runs the full test suite against the chain, adds any missing wrapper tests, and also adds the module-level docstring clarification to `default_operations.py`. Both tasks are low-risk confirmations, not new implementations.
**Delivers:** Confirmed complete XY delegation chain test coverage for `LDQubit`; confirmed absence of XY macros for `QuantumDot`; `OperationsRegistry` usage clarified in docstring and README.
**Files changed:** `operations/default_macros/single_qubit_macros.py` (validate only, add tests if missing); `operations/default_operations.py` (module-level docstring); `operations/README.md` (add QD/SD/QDP to component table).
**Avoids:** Pitfall 4 (delegation chain completeness — test explicitly verifies `XYDriveMacro` is present whenever `XMacro` is registered, and absent on `QuantumDot`).

### Phase 4: Customer-Facing Tutorial

**Rationale:** The tutorial is the final customer-facing deliverable and the highest-complexity remaining item. It requires Phases 1-3 to be complete because it must demonstrate working code. The tutorial must cover all four workflows in order (use defaults → type-level override → instance-level override → external macro package), include runnable snippets, and explain the `@quam_dataclass` constraint explicitly. Without this, the system is not discoverable by new lab customers.
**Delivers:** A structured tutorial document covering all four customization workflows, with runnable code, TOML schema examples, and explicit anti-patterns (XY macros on `QuantumDot`, non-`@quam_dataclass` custom classes).
**Files changed:** New tutorial file in `examples/` or `docs/` (location TBD); no production code changes.
**Avoids:** All "looks done but isn't" documentation failures from the PITFALLS.md checklist; tutorial structure pitfall (task-oriented, not module-oriented).

### Phase Ordering Rationale

- **Phase 1 before Phase 2:** Registration must exist before tests can assert on it. The `_reset_registration()` helper is added in Phase 1 so Phase 2 tests use it from the start.
- **Phase 2 before Phase 3:** Running the full test suite (Phase 3 first step) requires Phase 2 tests to exist so regressions are caught. Wrapper validation without QD tests would miss cross-type contamination.
- **Phase 3 before Phase 4:** Tutorial code must be demonstrably runnable; Phase 3 confirms the wrapper chain and OperationsRegistry work end-to-end before they appear in tutorial examples.
- **Phase grouping matches the architecture's natural units:** Catalog (registry layer) → Tests (validation layer) → Chain confirmation (macro class layer) → Docs (customer layer). This avoids writing documentation for unverified behavior.

### Research Flags

Phases with well-documented patterns (skip research-phase):
- **Phase 1:** Catalog registration is a direct three-line addition using the established `register_component_macro_factories()` + `STATE_POINT_MACROS` pattern. No ambiguity.
- **Phase 2:** Test patterns are established in `test_macro_wiring.py` and `test_macro_classes.py`; new tests mirror existing structure directly.
- **Phase 3:** Wrapper classes are confirmed present in `single_qubit_macros.py`; OperationsRegistry role is well-understood from reading `default_operations.py`.

Phases that may need targeted investigation during planning:
- **Phase 4 (Tutorial):** Tutorial location (examples/ vs docs/), format (Python script vs Markdown), and scope boundary (what to include vs reference to README) should be confirmed with the team before drafting. The FEATURES.md research flags notebook format as an anti-feature for this project, but customer expectations for the quantum hardware domain typically favor notebooks. This single decision affects CI integration and ongoing maintenance burden.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All findings from direct uv.lock and pyproject.toml inspection; no inference required |
| Features | HIGH | Gap confirmed by reading `component_macro_catalog.py` directly; all existing macro classes verified present in `single_qubit_macros.py` |
| Architecture | HIGH | Layer boundaries and data flow verified from live source files; MRO resolution behavior read directly from `macro_registry.py` |
| Pitfalls | HIGH | All pitfalls derived from reading actual source code patterns; `_REGISTERED` flag, `_owner_component()` heuristic, and delegation chain all inspected directly |

**Overall confidence:** HIGH

### Gaps to Address

- **Tutorial format decision:** Research reaches conflicting conclusions — domain convention favors Jupyter notebooks, but project-specific analysis flags them as a CI liability. Resolve before starting Phase 4 by checking how `qualibrate` and `qua-libs` deliver customer tutorials on this milestone's branch.
- **SensorDot separate registration:** Research concludes that MRO-based inheritance from `QuantumDot` is sufficient for `SensorDot` in the current scope (state macros only), and a separate explicit `SensorDot` registration is optional. The decision to register separately or rely on MRO should be made in Phase 1 and documented, as it affects future `SensorDot`-specific macro divergence patterns.
- **Single-qubit wrapper completeness:** ARCHITECTURE.md notes the wrapper classes "appear complete" but recommends confirming by test run. This is not a research gap — run `make test` at the start of Phase 3 to confirm or identify any missing class.

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `quam_builder/architecture/quantum_dots/operations/component_macro_catalog.py` — registration gap confirmed
- `quam_builder/architecture/quantum_dots/operations/default_macros/state_macros.py` — `STATE_POINT_MACROS` dict, `_owner_component()` heuristic
- `quam_builder/architecture/quantum_dots/operations/default_macros/single_qubit_macros.py` — full wrapper chain confirmed present
- `quam_builder/architecture/quantum_dots/operations/macro_registry.py` — MRO-aware resolution, module-level state
- `quam_builder/architecture/quantum_dots/macro_engine/wiring.py` — `_iter_macro_components` already includes QD collections
- `quam_builder/architecture/quantum_dots/components/quantum_dot.py`, `sensor_dot.py`, `quantum_dot_pair.py` — component structure confirmed voltage-only
- `quam_builder/architecture/quantum_dots/components/mixins/macro_dispatch.py` — dispatch cache invalidation, `_REGISTERED` guard
- `quam_builder/architecture/quantum_dots/operations/default_operations.py` — OperationsRegistry annotations, typed stubs
- `tests/builder/quantum_dots/test_macro_wiring.py` — established mock patterns for dispatch testing
- `uv.lock`, `pyproject.toml` — exact locked versions for all dependencies

### Secondary (MEDIUM confidence — inferred from patterns)
- Scientific Python tutorial conventions (QuTiP, Qiskit, PennyLane) — tutorial structure recommendation for four-workflow systems
- `nbmake` vs `nbval` notebook testing recommendation — standard pytest-native notebook runner choice

---
*Research completed: 2026-03-03*
*Ready for roadmap: yes*
