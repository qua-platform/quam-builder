---
phase: 1
slug: catalog-registration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-03
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 / 9.0.1 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/architecture/quantum_dots/components/ tests/builder/quantum_dots/test_macro_wiring.py -x -q` |
| **Full suite command** | `pytest tests/ -m "not server" -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/architecture/quantum_dots/components/ tests/builder/quantum_dots/test_macro_wiring.py -x -q`
- **After every plan wave:** Run `pytest tests/ -m "not server" -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | TEST-04 | fixture | `pytest tests/ -m "not server" -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | TEST-04 | unit | `pytest tests/ -m "not server" -q` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | CAT-01 | unit | `pytest tests/architecture/quantum_dots/components/test_quantum_dot.py -x -q` | ✅ | ⬜ pending |
| 1-01-04 | 01 | 1 | CAT-02 | unit | `pytest tests/architecture/quantum_dots/components/test_quantum_dot_pair.py -x -q` | ✅ | ⬜ pending |
| 1-01-05 | 01 | 1 | CAT-03 | unit | `pytest tests/architecture/quantum_dots/components/test_sensor_dot.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — add `reset_catalog` fixture (calls `_reset_registration()` + `_reset_registry()`); covers TEST-04
- [ ] `quam_builder/architecture/quantum_dots/operations/component_macro_catalog.py` — add `_reset_registration()` helper function
- [ ] `quam_builder/architecture/quantum_dots/operations/macro_registry.py` — add `_reset_registry()` helper function

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
