---
phase: 02-test-coverage
plan: 02
subsystem: testing
tags: [pytest, mock, qua, X180Macro, delegation-chain]

# Dependency graph
requires:
  - phase: 02-test-coverage
    provides: wire_machine_macros, _build_machine, _seed_reference_pulses
provides:
  - X180Macro smoke test (qua.program() produces valid prog)
  - X180Macro mock test (play_xy_pulse called with "x180")
affects: [02-test-coverage]

# Tech tracking
tech-stack:
  added: []
  patterns: [qua.program() smoke test, patch play_xy_pulse for delegation assertion]

key-files:
  created: []
  modified: [tests/builder/quantum_dots/test_macro_wiring.py]

key-decisions:
  - "Use _build_machine() (not qd_machine) per plan — qd_machine has no XY drive; qubits need XY for x180"

patterns-established:
  - "X180 delegation test pattern: wire_machine_macros + _seed_reference_pulses before apply()"
  - "Mock play_xy_pulse to assert delegation chain without QUA execution"

requirements-completed: [TEST-05]

# Metrics
duration: 15min
completed: "2026-03-03"
---

# Phase 2 Plan 2: X180Macro Delegation Chain Tests Summary

**X180Macro smoke and mock tests in test_macro_wiring.py — full delegation chain (X180Macro → XMacro → XYDriveMacro → play_xy_pulse) covered for TEST-05**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-03T23:35:00Z (approx)
- **Completed:** 2026-03-03T23:49:04Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- `test_x180_macro_produces_valid_qua_program`: smoke test calling `q1.macros["x180"].apply()` inside `qua.program()` and asserting `prog is not None`
- `test_x180_macro_triggers_play`: mock test patching `play_xy_pulse` and asserting it was called with `"x180"` when `apply()` runs
- Both use `_build_machine()`, `wire_machine_macros(machine, strict=True)`, and `_seed_reference_pulses(machine)` per plan

## Task Commits

Both tasks committed in a single atomic commit (same file, same requirement):

1. **Task 1: Add X180Macro smoke test** — `2dc6e19` (test)
2. **Task 2: Add X180Macro mock assertion test** — `2dc6e19` (test)

**Plan metadata:** `a88e52a` (docs: complete plan)

## Files Created/Modified

- `tests/builder/quantum_dots/test_macro_wiring.py` — Added `from qm import qua`, `test_x180_macro_produces_valid_qua_program`, `test_x180_macro_triggers_play`

## Decisions Made

- None — followed plan as specified. Used `_build_machine()` as directed (qd_machine lacks XY drive).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TEST-05 complete. Ready for 02-03-PLAN (save/load round-trip test).
- Full builder + architecture test suite passes (310 tests).

## Self-Check: PASSED

- 02-02-SUMMARY.md exists
- Commit 2dc6e19 exists (test: X180Macro delegation chain tests)

---
*Phase: 02-test-coverage*
*Completed: 2026-03-03*
