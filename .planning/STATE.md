# State: quam-builder

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-03)

**Core value:** Customers can build complete, correct QUAM configurations without manually managing low-level hardware wiring — and customize gate behavior without forking the library.
**Current focus:** Phase 1 — Catalog Registration

## Current Position

Phase: 1 of 4 (Catalog Registration)
Plan: — of TBD in current phase
Status: Ready to plan
Last activity: 2026-03-03 — Roadmap created for v1.0 QD Operations milestone

Progress: [░░░░░░░░░░] 0%

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

## Accumulated Context

### Decisions

- Working branch: `feature/qd_default_operations`
- Core `wire_machine_macros` API and macro registry already implemented on this branch
- Component catalog covers QPU, LDQubit, LDQubitPair — QuantumDot/SensorDot/QuantumDotPair are the main gap
- State macros and XYDriveMacro have real QUA implementations; two-qubit gate macros are explicit placeholders
- TEST-04 (registry reset fixture) grouped with Phase 1 so fixture exists before any new catalog tests are written in Phase 2
- SensorDot separate vs MRO-inherited registration: decision deferred to Phase 1 planning (document the choice)

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 4 tutorial format (Jupyter notebook vs Python script) flagged in research as unresolved — DOCS-01 requests a notebook, DOCS-02 requests a script; confirm notebook is acceptable for this project before starting Phase 4 planning

## Session Continuity

Last session: 2026-03-03
Stopped at: Roadmap created — ready to plan Phase 1
Resume file: None
