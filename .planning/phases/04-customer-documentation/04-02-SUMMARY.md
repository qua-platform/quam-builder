---
phase: 04-customer-documentation
plan: 02
subsystem: documentation
tags: [macro-overrides, wire_machine_macros, external-package, @quam_dataclass]
requires:
  - phase: 04-customer-documentation
    provides: build_tutorial_machine, tutorials/README.md, macro_customization.ipynb
provides:
  - quam_builder/architecture/quantum_dots/examples/external_macro_package_example.py
  - quam_builder/architecture/quantum_dots/examples/external_macro_demo/ (catalog.py, __init__.py)
affects: []
tech-stack:
  added: []
  patterns: [external macro package, build_macro_overrides, lab-owned macro catalog]
key-files:
  created:
    - quam_builder/architecture/quantum_dots/examples/external_macro_package_example.py
    - quam_builder/architecture/quantum_dots/examples/external_macro_demo/__init__.py
    - quam_builder/architecture/quantum_dots/examples/external_macro_demo/catalog.py
  modified: []
key-decisions:
  - "LabInitializeMacro extends InitializeStateMacro with lab_ramp_duration for parametrization"
  - "Script uses sys.path fix so it runs when executed directly (python path/to/script.py)"
requirements-completed: [DOCS-02]
duration: ~10 min
completed: 2026-03-03
---

# Phase 4 Plan 2: External Macro Package Example Summary

**Standalone Python script and external_macro_demo package demonstrating lab-owned macro catalog workflow — runs without QM hardware**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2
- **Files created:** 3 (external_macro_package_example.py, external_macro_demo/__init__.py, catalog.py)

## Accomplishments

- external_macro_demo package with LabInitializeMacro (@quam_dataclass) and build_macro_overrides()
- Standalone script imports build_macro_overrides, builds tutorial machine (QuantumDot, QuantumDotPair, SensorDot), wires macros, builds QUA program, exits 0
- Script runs directly: `python quam_builder/architecture/quantum_dots/examples/external_macro_package_example.py` — no QM hardware required

## Task Commits

1. **Task 1: Create external macro demo subpackage** — `6ff5766` (feat) — external_macro_demo/__init__.py, catalog.py
2. **Task 2: Create external_macro_package_example.py script** — `83dc510` (feat)

## Files Created/Modified

- `quam_builder/architecture/quantum_dots/examples/external_macro_package_example.py` — Main script; imports build_macro_overrides, builds machine, wires macros, builds QUA program
- `quam_builder/architecture/quantum_dots/examples/external_macro_demo/__init__.py` — Exports build_macro_overrides, LabInitializeMacro
- `quam_builder/architecture/quantum_dots/examples/external_macro_demo/catalog.py` — LabInitializeMacro (extends InitializeStateMacro, lab_ramp_duration), build_macro_overrides()

## Decisions Made

- LabInitializeMacro adds lab_ramp_duration (default 64) for parametrization; build_macro_overrides passes params.lab_ramp_duration=80
- Script includes sys.path fix for direct execution from project root
- QuantumDot.initialize override only (plan allowed optionally QuantumDotPair, SensorDot — defaults suffice for demo)

## Deviations from Plan

None — plan executed as specified.

## Issues Encountered

None.

## Next Phase Readiness

Phase 4 complete. Both plans (04-01 notebook, 04-02 script) delivered.

---
*Phase: 04-customer-documentation*
*Completed: 2026-03-03*
