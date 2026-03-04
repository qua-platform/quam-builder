# Roadmap: quam-builder

## Overview

Milestone v1.0 — QD Operations closes the component catalog gap for `QuantumDot`, `SensorDot`, and `QuantumDotPair`. The macro system infrastructure (registry, wiring engine, state macro classes) is already implemented on `feature/qd_default_operations`. This milestone adds the three missing catalog registrations, hardens the test suite against cross-test state contamination, confirms the full delegation chain for existing qubit macros, clarifies the OperationsRegistry role in documentation, and delivers customer-facing tutorials for all four macro customization workflows.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Catalog Registration** - Register QuantumDot, QuantumDotPair, and SensorDot in the component catalog with state macros; add registry reset fixture
- [ ] **Phase 2: Test Coverage** - Assert macro presence and behavior for all three new component types; cover existing LDQubit delegation chain and save/load round-trips
- [ ] **Phase 3: OperationsRegistry Clarification** - Add module docstring and README table clarifying the three dispatch paths
- [ ] **Phase 4: Customer Documentation** - Jupyter notebook tutorial and Python script example covering all four macro customization workflows

## Phase Details

### Phase 1: Catalog Registration
**Goal**: `QuantumDot`, `QuantumDotPair`, and `SensorDot` each receive their default state macros (`initialize`, `measure`, `empty` where applicable) after a call to `wire_machine_macros(machine)`, and cross-test catalog state contamination is eliminated
**Depends on**: Nothing (first phase)
**Requirements**: CAT-01, CAT-02, CAT-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Calling `wire_machine_macros(machine)` on a machine with `QuantumDot` components populates `component.macros` with `initialize`, `measure`, and `empty` keys
  2. Calling `wire_machine_macros(machine)` on a machine with `QuantumDotPair` components populates `component.macros` with `initialize`, `measure`, and `empty` keys
  3. Calling `wire_machine_macros(machine)` on a machine with `SensorDot` components populates `component.macros` with a `measure` key and no `initialize` or `empty` keys
  4. A pytest fixture exists that resets the catalog `_REGISTERED` flag between test functions, preventing state leakage across the full test suite
**Plans**: TBD

### Phase 2: Test Coverage
**Goal**: The test suite asserts correct macro presence and invocation behavior for all three new component types, the `LDQubit` XY delegation chain, and save/load round-trips — providing regression protection for the full macro system
**Depends on**: Phase 1
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-05, TEST-06
**Success Criteria** (what must be TRUE):
  1. Running `make test` produces passing assertions that `QuantumDot.macros` contains `initialize`, `measure`, and `empty` after wiring
  2. Running `make test` produces passing assertions that `QuantumDotPair.macros` contains `initialize`, `measure`, and `empty` after wiring
  3. Running `make test` produces passing assertions that `SensorDot.macros` contains `measure` but not `initialize` or `empty` after wiring
  4. The `LDQubit` delegation chain (`X180Macro` → `XMacro` → `XYDriveMacro`) is covered by a test that calls `macro.apply()` end-to-end and asserts the correct QUA method was invoked
  5. A save/load round-trip test for `QuantumDot`, `QuantumDotPair`, and `SensorDot` macro instances completes without error and the restored macros are functionally equivalent
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Verify catalog tests pass; mark TEST-01/02/03 complete
- [x] 02-02-PLAN.md — Add X180Macro smoke + mock tests (TEST-05)
- [ ] 02-03-PLAN.md — Add save/load round-trip test (TEST-06)

### Phase 3: OperationsRegistry Clarification
**Goal**: Developers reading `default_operations.py` and `operations/README.md` understand when to use `operations_registry.x(q)` vs `q.x()` vs `q.macros["x"].apply()` without ambiguity
**Depends on**: Phase 2
**Requirements**: OPS-01, OPS-02
**Success Criteria** (what must be TRUE):
  1. The `OperationsRegistry` module docstring in `default_operations.py` explains its role relative to direct component method dispatch in 3-5 sentences with concrete examples
  2. `operations/README.md` contains a table with three rows — `operations_registry.x180(q)`, `q.x180()`, `q.macros["x180"].apply()` — each with a "when to use" column and applicable component types
**Plans**: 1 plan

Plans:
- [ ] 03-01-PLAN.md — Add module docstring (OPS-01) and README comparison table (OPS-02)

### Phase 4: Customer Documentation
**Goal**: A new lab customer can discover and use all four macro customization workflows (use defaults / type-level override / instance-level override / external macro package) from the tutorial alone, without reading library source code
**Depends on**: Phase 3
**Requirements**: DOCS-01, DOCS-02
**Success Criteria** (what must be TRUE):
  1. A Jupyter notebook tutorial exists that runs end-to-end without QM hardware, covering all four customization workflows in order with working code cells
  2. The tutorial explicitly demonstrates the `@quam_dataclass` constraint for custom macro classes and shows the anti-pattern (non-decorated class) alongside the correct form
  3. A standalone Python script example exists demonstrating the external macro package workflow with a self-contained importable macro class
  4. Both the notebook and script reference the correct component types (`QuantumDot`, `QuantumDotPair`, `SensorDot`) and produce no runtime errors when executed
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Catalog Registration | 2/2 | Complete | 2026-03-03 |
| 2. Test Coverage | 1/3 | In Progress | - |
| 3. OperationsRegistry Clarification | 0/1 | Not started | - |
| 4. Customer Documentation | 0/TBD | Not started | - |
