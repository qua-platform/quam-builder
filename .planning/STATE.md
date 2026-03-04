---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: completed
stopped_at: Completed 04-customer-documentation-04-01-PLAN.md
last_updated: "2026-03-04T00:33:07.665Z"
last_activity: 2026-03-04 — Completed 03-01 OperationsRegistry docstring + README table
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 8
  completed_plans: 7
  percent: 88
---

# State: quam-builder

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-03)

**Core value:** Customers can build complete, correct QUAM configurations without manually managing low-level hardware wiring — and customize gate behavior without forking the library.
**Current focus:** Phase 1 — Catalog Registration

## Current Position

Phase: 4 of 4 (Customer Documentation)
Plan: 1 of 2 in current phase
Status: Phase 4 in progress (04-01 complete)
Last activity: 2026-03-04 — Completed 04-01 macro customization notebook tutorial

Progress: [█████████░] 88%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-catalog-registration P01 | 20 | 3 tasks | 6 files |
| Phase 01-catalog-registration P02 | 15 | 2 tasks | 6 files |
| Phase 02-test-coverage P01 | 3min | 1 tasks | 1 files |
| Phase 02-test-coverage P03 | 5min | 1 tasks | 1 files |
| Phase 02-test-coverage P02 | 15 | 2 tasks | 1 files |
| Phase 03-operationsregistry-clarification P01 | 6min | 2 tasks | 2 files |
| Phase 04-customer-documentation P01 | 15 min | 3 tasks | 5 files |

## Accumulated Context

### Decisions

- Working branch: `feature/qd_default_operations`
- Core `wire_machine_macros` API and macro registry already implemented on this branch
- Component catalog covers QPU, LDQubit, LDQubitPair — QuantumDot/SensorDot/QuantumDotPair are the main gap
- State macros and XYDriveMacro have real QUA implementations; two-qubit gate macros are explicit placeholders
- TEST-04 (registry reset fixture) grouped with Phase 1 so fixture exists before any new catalog tests are written in Phase 2
- SensorDot separate vs MRO-inherited registration: decision deferred to Phase 1 planning (document the choice)
- [Phase 01-catalog-registration]: SensorDotMeasureMacro uses QuamMacro (not QubitMacro) — SensorDot is voltage-only
- [Phase 01-catalog-registration]: reset_catalog fixture autouse=False to avoid breaking registration-dependent tests
- [Phase 01-catalog-registration]: SensorDot replace=True implemented in macro_registry — _REPLACE_KEYS prevents MRO inheritance
- [Phase 04-customer-documentation]: Use InitializeStateMacro from library (not notebook-defined GoodMacro) for @quam_dataclass demo — notebook-defined classes lack module path

### Pending Todos

None yet.

### Blockers/Concerns

- None (DOCS-01 complete; notebook format validated)

## Session Continuity

Last session: 2026-03-04T00:33:04.711Z
Stopped at: Completed 04-customer-documentation-04-01-PLAN.md
Resume file: None
