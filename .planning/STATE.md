# State: quam-builder

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-03 — Milestone v1.0 QD Operations started

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-03)

**Core value:** Customers can build complete, correct QUAM configurations without manually managing low-level hardware wiring — and customize gate behavior without forking the library.
**Current focus:** v1.0 — QD Operations

## Accumulated Context

- Working branch: `feature/qd_default_operations`
- The core `wire_machine_macros` API and macro registry are already implemented on this branch
- Component catalog covers QPU, LDQubit, LDQubitPair — QuantumDot/SensorDot/QuantumDotPair are the main gap
- State macros and XYDriveMacro have real QUA implementations; two-qubit gate macros are explicit placeholders
- Technical README exists at `quam_builder/architecture/quantum_dots/operations/README.md`
- Two working examples exist in `quam_builder/architecture/quantum_dots/examples/`
