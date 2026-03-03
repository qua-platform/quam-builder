# Requirements: quam-builder

**Defined:** 2026-03-03
**Core Value:** Customers can build complete, correct QUAM configurations without manually managing low-level hardware wiring — and customize gate behavior without forking the library.

## v1 Requirements

Requirements for milestone v1.0 — QD Operations. Each maps to roadmap phases.

### Catalog Registration

- [x] **CAT-01**: `QuantumDot` is registered in the component catalog with state macros (`initialize`, `measure`, `empty`) — voltage-based, delegating to the dot's preferred `QuantumDotPair` macro
- [x] **CAT-02**: `QuantumDotPair` is registered in the component catalog with its own state macro implementations (`initialize`, `measure`, `empty`)
- [x] **CAT-03**: `SensorDot` is registered in the component catalog with a `measure` macro dispatching via the readout resonator — no `initialize` or `empty`

### Tests

- [x] **TEST-01**: `QuantumDot` default macros (`initialize`, `measure`, `empty`) are asserted in tests using the existing mock pattern
- [x] **TEST-02**: `QuantumDotPair` default macros are asserted in tests
- [x] **TEST-03**: `SensorDot` default `measure` macro is asserted; `initialize`/`empty` are absent from its catalog entry
- [x] **TEST-04**: Registry reset fixture/helper added to prevent `_REGISTERED` flag contaminating cross-test state
- [ ] **TEST-05**: `LDQubit` single-qubit delegation chain (`X180Macro → XMacro → XYDriveMacro`) is covered by end-to-end test
- [x] **TEST-06**: Save/load round-trip test for `QuantumDot`, `QuantumDotPair`, and `SensorDot` macro instances

### OperationsRegistry

- [ ] **OPS-01**: `OperationsRegistry` module docstring clarifies its role relative to direct `component.x180()` dispatch
- [ ] **OPS-02**: Operations `README.md` includes a table clarifying `operations_registry.x180(q)` vs `q.x180()` vs `q.macros["x180"].apply()`

### Documentation

- [ ] **DOCS-01**: Jupyter notebook tutorial covering all four customer workflows: use defaults / type-level override / instance-level override / external package — executable without QM hardware
- [ ] **DOCS-02**: Python script example demonstrating the external macro package workflow

## v2 Requirements

Deferred to a future milestone.

### SensorDot Extended Macros

- **SENS-01**: `SensorDot` `initialize` macro (if a distinct voltage preparation sequence is needed separate from dot pair)
- **SENS-02**: `SensorDot` `empty` macro (if required by experimental protocol)

### Extended Macro Coverage

- **EXT-01**: `QuantumDotMacroName` enum for voltage-only component macro names (consistent with `SingleQubitMacroName`)
- **EXT-02**: `nbmake` CI integration for notebook tutorial validation

## Out of Scope

| Feature | Reason |
|---------|--------|
| Superconducting macro system | Independent architecture — not in this milestone |
| NV center macro system | Not yet scoped |
| Neutral atoms architecture | Not yet started |
| Working QUA implementations for 2Q gates (cnot, cz, swap, iswap) | Explicit placeholders — users supply calibrated logic via overrides |
| SensorDot `initialize`/`empty` macros | Deferred — readout resonator path for measure is the immediate need |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CAT-01 | Phase 1 | Complete |
| CAT-02 | Phase 1 | Complete |
| CAT-03 | Phase 1 | Complete |
| TEST-04 | Phase 1 | Complete |
| TEST-01 | Phase 2 | Complete |
| TEST-02 | Phase 2 | Complete |
| TEST-03 | Phase 2 | Complete |
| TEST-05 | Phase 2 | Pending |
| TEST-06 | Phase 2 | Complete |
| OPS-01 | Phase 3 | Pending |
| OPS-02 | Phase 3 | Pending |
| DOCS-01 | Phase 4 | Pending |
| DOCS-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 — traceability filled by roadmap creation*
