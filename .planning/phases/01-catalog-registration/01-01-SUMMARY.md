---
phase: 01-catalog-registration
plan: 01
subsystem: testing
tags: [pytest, macro-registry, catalog, state-macros]

# Dependency graph
requires: []
provides:
  - _reset_registration() and _reset_registry() for test isolation
  - reset_catalog pytest fixture
  - SensorDotMeasureMacro class for Plan 02 SensorDot registration
affects: [01-02-catalog-registration]

# Tech tracking
tech-stack:
  added: []
  patterns: [TDD red-green-refactor, generator fixtures, FOR TESTING ONLY convention]

key-files:
  created:
    - tests/architecture/quantum_dots/operations/test_catalog_reset.py
  modified:
    - quam_builder/architecture/quantum_dots/operations/component_macro_catalog.py
    - quam_builder/architecture/quantum_dots/operations/macro_registry.py
    - quam_builder/architecture/quantum_dots/operations/default_macros/state_macros.py
    - tests/conftest.py
    - tests/architecture/quantum_dots/components/test_sensor_dot.py

key-decisions:
  - "SensorDotMeasureMacro uses QuamMacro directly (not QubitMacro) — SensorDot is not a Qubit"
  - "reset_catalog fixture has autouse=False — only tests verifying registration state use it"

patterns-established:
  - "FOR TESTING ONLY: Private reset helpers documented for test isolation; not exported via __all__"
  - "Generator fixture (yield) for reset_catalog allows future teardown without changing call sites"

requirements-completed: [TEST-04]

# Metrics
duration: ~20 min
completed: "2026-03-03"
---

# Phase 1 Plan 1: Catalog Registration Infrastructure Summary

**Test-isolation infrastructure: _reset_registration/_reset_registry helpers, reset_catalog fixture, and SensorDotMeasureMacro for Plan 02**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-03-03
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `_reset_registration()` in component_macro_catalog.py sets `_REGISTERED = False`
- `_reset_registry()` in macro_registry.py clears `_COMPONENT_MACRO_FACTORIES`
- `SensorDotMeasureMacro` in state_macros.py with `@quam_dataclass`, `apply()` dispatches to `owner.readout_resonator.measure(*args, **kwargs)`
- `reset_catalog` pytest fixture in tests/conftest.py calls both reset helpers, `autouse=False`
- Full test suite passes: `pytest tests/ -m "not server" -q` (373 passed, 3 skipped)

## Task Commits

Each task was committed atomically (TDD: test → feat):

1. **Task 1: Reset helpers** - `a80e0d9` (test), `90fc1dc` (feat)
2. **Task 2: SensorDotMeasureMacro** - `53be7fe` (test), `35331e4` (feat)
3. **Task 3: reset_catalog fixture** - `f2bd53d` (feat)

**Plan metadata:** docs commit (complete plan)

## Files Created/Modified

- `tests/architecture/quantum_dots/operations/test_catalog_reset.py` — New tests for reset helpers and fixture
- `quam_builder/architecture/quantum_dots/operations/component_macro_catalog.py` — _reset_registration()
- `quam_builder/architecture/quantum_dots/operations/macro_registry.py` — _reset_registry()
- `quam_builder/architecture/quantum_dots/operations/default_macros/state_macros.py` — SensorDotMeasureMacro
- `tests/conftest.py` — reset_catalog fixture
- `tests/architecture/quantum_dots/components/test_sensor_dot.py` — TestSensorDotMeasureMacro tests

## Decisions Made

- SensorDotMeasureMacro subclasses QuamMacro directly (not QubitMacro) — SensorDot is voltage-only, not a Qubit
- reset_catalog autouse=False — prevents breaking tests that rely on registration during component construction
- Both reset helpers marked "FOR TESTING ONLY" in docstrings; not exported via __all__

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 02 (01-02): Register QuantumDot, QuantumDotPair, and SensorDot in component_macro_catalog. SensorDotMeasureMacro is now available for the SensorDot `{measure: SensorDotMeasureMacro}` registration.

## Self-Check: PASSED

- 01-01-SUMMARY.md exists
- All task commits present: a80e0d9, 90fc1dc, 53be7fe, 35331e4, f2bd53d

---
*Phase: 01-catalog-registration*
*Completed: 2026-03-03*
