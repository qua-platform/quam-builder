---
phase: 4
slug: customer-documentation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + manual execution |
| **Config file** | pyproject.toml |
| **Quick run command** | `python tutorials/macro_customization_demo.py 2>&1 | tail -5` (once created) |
| **Full suite command** | `make test` (regression guard) |
| **Estimated runtime** | ~60 seconds (full suite + script execution) |

---

## Sampling Rate

- **After every task commit:** Run `make test` to confirm no regressions
- **After notebook task:** Execute all notebook cells manually (or `jupyter nbconvert --to notebook --execute`) and confirm no errors
- **After script task:** Run `python <script_path>` and confirm exit code 0
- **Phase gate:** Notebook runs end-to-end without errors; script exits 0; both reference correct component types

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | DOCS-01 | automated + manual | `jupyter nbconvert --to notebook --execute tutorials/macro_customization.ipynb --output /tmp/test_nb.ipynb 2>&1 \| tail -5` | ❌ Wave 0 | ⬜ pending |
| 4-01-02 | 02 | 2 | DOCS-02 | automated | `python quam_builder/architecture/quantum_dots/examples/external_macro_package_example.py 2>&1 \| tail -5` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tutorials/` directory at repo root (for notebook)
- [ ] `tutorials/macro_customization.ipynb` — new notebook file
- [ ] `quam_builder/architecture/quantum_dots/examples/external_macro_package_example.py` — new script file (Wave 2)
- [ ] Jupyter installed in test env (`jupyter nbconvert`) for notebook validation

*Framework regression suite: `make test` already present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Notebook covers all four workflows in logical order and is readable end-to-end | DOCS-01 | Content quality judgment | Open notebook, read narrative cells; verify workflow order: defaults → type-level → instance-level → external package |
| `@quam_dataclass` anti-pattern is clearly shown alongside the correct form | DOCS-01 | Pedagogical clarity judgment | Find the anti-pattern cell; confirm it shows a broken (non-decorated) class and explains why it fails |
| Script is self-contained and importable | DOCS-02 | Structural judgment | Verify script does not depend on experiment-specific file paths or running QOP |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify
- [ ] Sampling continuity: `make test` after each task
- [ ] Wave 0 (directory + file stubs) covered before coding tasks
- [ ] Notebook executes end-to-end without errors
- [ ] Script exits 0
- [ ] No `qm.open()`, `qm.run()`, or hardware connection calls
- [ ] `nyquist_compliant: true` set in frontmatter after review

**Approval:** pending
