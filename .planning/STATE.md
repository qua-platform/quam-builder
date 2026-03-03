---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
stopped_at: Completed 01-02-PLAN.md
last_updated: "2026-03-03T22:46:08.834Z"
last_activity: 2026-03-03 — Roadmap created for v1.0 QD Operations milestone
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 2
  completed_plans: 2
  percent: 50
---

# State: quam-builder

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-03)

**Core value:** Customers can build complete, correct QUAM configurations without manually managing low-level hardware wiring — and customize gate behavior without forking the library.
**Current focus:** Phase 1 — Catalog Registration

## Current Position

Phase: 1 of 4 (Catalog Registration)
Plan: 2 of 2 in current phase
Status: Phase 1 complete
Last activity: 2026-03-03 — Completed 01-02 catalog registration

Progress: [██████████] 100%

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

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 4 tutorial format (Jupyter notebook vs Python script) flagged in research as unresolved — DOCS-01 requests a notebook, DOCS-02 requests a script; confirm notebook is acceptable for this project before starting Phase 4 planning

## Session Continuity

Last session: 2026-03-03T22:46:08.831Z
Stopped at: Completed 01-02-PLAN.md
Resume file: None
