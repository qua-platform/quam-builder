---
phase: 01-catalog-registration
plan: 02
subsystem: catalog
tags: [macro-registry, quantum-dot, sensor-dot, state-macros, CAT-01, CAT-02, CAT-03]

# Dependency graph
requires:
  - phase: 01-01
    provides: _reset_registration, _reset_registry, reset_catalog fixture, SensorDotMeasureMacro
provides:
  - QuantumDot, QuantumDotPair, SensorDot registered in component macro catalog
  - replace=True MRO semantics in macro_registry for SensorDot measure-only
affects: [02-test-coverage, 04-documentation]

# Tech tracking
tech-stack:
  added: []
  patterns: [lazy imports in catalog, replace semantics for MRO override]

key-files:
  created: []
  modified:
    - quam_builder/architecture/quantum_dots/operations/component_macro_catalog.py
    - quam_builder/architecture/quantum_dots/operations/macro_registry.py
    - tests/architecture/quantum_dots/components/test_quantum_dot.py
    - tests/architecture/quantum_dots/components/test_quantum_dot_pair.py
    - tests/architecture/quantum_dots/components/test_sensor_dot.py
    - tests/macros/test_macro_fluent_api.py

key-decisions:
  - "SensorDot registered with replace=True + measure-only dict; macro_registry implements replace semantics by resetting resolved to utility-only when hitting replace type"

patterns-established:
  - "replace=True in register_component_macro_factories prevents MRO inheritance for that type"

requirements-completed: [CAT-01, CAT-02, CAT-03]

# Metrics
duration: ~15 min
completed: "2026-03-03"
---

# Phase 1 Plan 2: Catalog Registration Gap Closure Summary

**QuantumDot, QuantumDotPair, and SensorDot registered in component macro catalog with state macros; SensorDot measure-only via replace=True**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-03-03
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `register_default_component_macro_factories()` now registers QuantumDot and QuantumDotPair with STATE_POINT_MACROS (initialize, measure, empty)
- SensorDot registered with {measure: SensorDotMeasureMacro} and replace=True — measure-only, no initialize/empty (CAT-03)
- macro_registry: implement replace=True MRO semantics — when a type is registered with replace, get_default_macro_factories resets to utility-only for that type (no inheritance from bases)
- TestQuantumDotCatalog, TestQuantumDotPairCatalog, TestSensorDotCatalog assert correct macro presence after wire_machine_macros()
- Full suite passes: pytest tests/ -m "not server" -q (382 passed, 3 skipped)

## Task Commits

Each task was committed atomically:

1. **Task 1: Catalog registrations** - `7ad6f72` (feat)
2. **Fix: replace=True MRO semantics** - `1870f0b` (fix) — deviation
3. **Task 2: Catalog test classes** - `9d460f6` (test)

**Plan metadata:** docs commit (complete plan)

## Files Created/Modified

- `component_macro_catalog.py` — Three new register_component_macro_factories() calls; lazy imports for QuantumDot, QuantumDotPair, SensorDot, SensorDotMeasureMacro
- `macro_registry.py` — _REPLACE_KEYS, get_default_macro_factories replace semantics, _reset_registry clears _REPLACE_KEYS
- `test_quantum_dot.py` — TestQuantumDotCatalog (3 tests: initialize, measure, empty)
- `test_quantum_dot_pair.py` — TestQuantumDotPairCatalog (3 tests: initialize, measure, empty)
- `test_sensor_dot.py` — TestSensorDotCatalog (3 tests: measure present, no initialize, no empty)
- `test_macro_fluent_api.py` — Updated test_complete_fluent_workflow expected macro count (9 → 12)

## Decisions Made

- SensorDot uses replace=True to override MRO-inherited QuantumDot factories — ensures CAT-03 (measure only)
- macro_registry stores replace flag per type; resolution resets when encountering replace type (no merge from bases)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] replace=True did not prevent MRO inheritance**
- **Found during:** Task 2 (TestSensorDotCatalog test_no_initialize_macro)
- **Issue:** SensorDot received initialize/empty from QuantumDot despite replace=True — get_default_macro_factories always merged base factories
- **Fix:** Added _REPLACE_KEYS; when iterating MRO, if type has replace registration, reset resolved to UTILITY and add only that type's factories
- **Files modified:** quam_builder/architecture/quantum_dots/operations/macro_registry.py
- **Verification:** TestSensorDotCatalog.test_no_initialize_macro and test_no_empty_macro pass
- **Commit:** 1870f0b

**2. [Rule 1 - Bug] test_complete_fluent_workflow expected wrong macro count**
- **Found during:** Full suite run
- **Issue:** Assertion len(qd.macros) == 9; now 12 (added initialize, measure, empty from new registration)
- **Fix:** Updated assertion to 12 with comment
- **Files modified:** tests/macros/test_macro_fluent_api.py
- **Verification:** Full suite passes
- **Commit:** 9d460f6 (part of Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Necessary for correctness. replace=True semantics were specified in plan but not implemented in registry; test assertion reflected pre-registration state.

## Issues Encountered

None beyond deviations.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Phase 1 complete. Ready for Phase 2 (Test Coverage) — catalog registration is done; Phase 2 will add macro invocation behavior tests and save/load round-trip coverage.

## Self-Check: PASSED

- 01-02-SUMMARY.md exists
- All task commits present: 7ad6f72, 1870f0b, 9d460f6

---
*Phase: 01-catalog-registration*
*Completed: 2026-03-03*
