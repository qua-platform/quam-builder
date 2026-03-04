---
phase: 04-customer-documentation
plan: 01
subsystem: documentation
tags: [jupyter, nbconvert, macro-customization, wire_machine_macros, tutorials]
requires: []
provides:
  - tutorials/README.md
  - tutorials/macro_customization.ipynb
  - build_tutorial_machine() in quam_builder.architecture.quantum_dots.examples.tutorial_machine
affects: []
tech-stack:
  added: [nbconvert]
  patterns: [macro override workflows, @quam_dataclass constraint]
key-files:
  created:
    - tutorials/README.md
    - tutorials/macro_customization.ipynb
    - quam_builder/architecture/quantum_dots/examples/tutorial_machine.py
  modified:
    - pyproject.toml
    - uv.lock
key-decisions:
  - "Use InitializeStateMacro from library (not notebook-defined GoodMacro) for @quam_dataclass demo — notebook-defined classes lack module path and fail on load"
requirements-completed: [DOCS-01]
duration: ~15 min
completed: 2026-03-04
---

# Phase 4 Plan 1: Customer Documentation Summary

**Jupyter notebook tutorial for macro customization covering four workflows, @quam_dataclass constraint, and shared machine builder — runs without QM hardware**

## Performance

- **Duration:** ~15 min
- **Tasks:** 3
- **Files modified:** 5 (pyproject.toml, uv.lock, tutorials/README.md, tutorial_machine.py, macro_customization.ipynb)

## Accomplishments

- Added nbconvert to dev dependencies for notebook verification
- Created tutorials/README.md with intro and link to macro_customization.ipynb
- Implemented build_tutorial_machine() with 2 quantum dots, 1 pair, 1 sensor, 2 qubits, 1 qubit pair
- Voltage step points (initialize, measure, empty) for state macros
- Jupyter notebook with all four workflows in order:
  1. Use defaults — wire_machine_macros(machine)
  2. Type-level override — QuantumDot initialize → CustomInitMacro
  3. Instance-level override — quantum_dots.virtual_dot_1 only
  4. External package — build_macro_overrides() pattern
- @quam_dataclass anti-pattern: BadMacro (notebook-defined) fails load; InitializeStateMacro (library) survives
- Notebook executes end-to-end via `jupyter nbconvert --to notebook --execute`

## Task Commits

1. **Task 1: Add nbconvert and create tutorials scaffold** — `f78b82e` (chore)
2. **Task 2: Create shared tutorial machine builder** — `5ef912b` (feat)
3. **Task 3: Create Jupyter notebook** — `3fb4870` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] sd.measure() requires pulse_name**
- **Found during:** Task 3
- **Issue:** SensorDot.measure() delegates to readout_resonator.measure() which requires pulse_name
- **Fix:** Use sd.measure('readout') in the QUA program
- **Files modified:** tutorials/macro_customization.ipynb

**2. [Rule 3 - Blocking] @quam_dataclass demo: notebook-defined GoodMacro fails load**
- **Found during:** Task 3
- **Issue:** Classes defined in a notebook lack a module path; QuAM deserialization requires `module.Class` form
- **Fix:** Use InitializeStateMacro from the library for the "good" case instead of a notebook-defined GoodMacro
- **Rationale:** The plan specified "BadMacro (no decorator) and GoodMacro (@quam_dataclass)" — both fail if notebook-defined. The key constraint is: @quam_dataclass + proper module. Demo now shows BadMacro (notebook) → fail; InitializeStateMacro (library) → survive.
- **Files modified:** tutorials/macro_customization.ipynb

---

**Total deviations:** 2 auto-fixed (both blocking)
**Impact:** Necessary for notebook to run and for @quam_dataclass demo to correctly illustrate the constraint.

## Self-Check: PASSED

- [ -f tutorials/README.md ]
- [ -f tutorials/macro_customization.ipynb ]
- [ -f quam_builder/architecture/quantum_dots/examples/tutorial_machine.py ]
- jupyter nbconvert --to notebook --execute tutorials/macro_customization.ipynb exits 0
- git log shows f78b82e, 5ef912b, 3fb4870

## Next Phase Readiness

Phase 4 Plan 1 complete. Ready for 04-02 (external macro package script) if applicable.
