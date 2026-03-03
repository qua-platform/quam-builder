# Stack Research

**Domain:** Python library for quantum hardware abstraction (QOP macro system)
**Researched:** 2026-03-03
**Confidence:** HIGH (based on direct codebase inspection; no web searches available)

---

## Scope Reminder

This is a SUBSEQUENT MILESTONE research document. The stack below covers only
additions or changes needed for the three NEW deliverables:

1. Registering `QuantumDot`, `SensorDot`, `QuantumDotPair` in the component catalog
2. Completing single-qubit macro wrapper implementations
3. Customer-facing documentation and tutorials

The existing stack (quam, qm-qua, qualang-tools, xarray, qcodes-contrib-drivers,
qm-saas, ruff, mypy, pytest, pytest-mock, pytest-cov) is locked and working.
Do NOT add new runtime dependencies.

---

## Existing Stack (Locked — Do Not Change)

| Package | Locked Version | Role |
|---------|---------------|------|
| quam | 0.5.0a2 | QuamMacro, quam_dataclass, QubitMacro, QubitPairMacro base classes |
| qm-qua | 1.2.3.1 | QUA program context, DSL (wait, play, assign, frame_rotation_2pi) |
| pytest | 8.4.2 / 9.0.1 | Test runner (version varies by Python target) |
| pytest-mock | 3.15.1 | patch.object for mocking voltage_sequence, virtual_z, play_xy_pulse |
| pytest-cov | 7.0.0 | Coverage gating |
| ruff | 0.14.11 | Formatting + linting (100-char line length, ruff-format) |
| mypy | 1.19.1 | Type checking |

**Source:** `uv.lock` (file inspection, HIGH confidence)

---

## Recommended Stack for New Work

### Core Technologies

No new runtime dependencies are needed or recommended. All three deliverables
are achievable with what is already installed.

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| quam (existing) | 0.5.0a2 | `QuamMacro`, `quam_dataclass`, `QuantumComponent` | `QuantumDot`/`SensorDot`/`QuantumDotPair` already subclass `VoltageMacroMixin` which inherits `MacroDispatchMixin(QuantumComponent)`. `@quam_dataclass` is the serialization contract — all new macro classes must use it. |
| Python stdlib `tomllib` (existing) | 3.11+ stdlib | TOML profile loading in `wire_machine_macros` | Already used in `macro_engine/wiring.py`. No third-party TOML lib needed. |
| Python stdlib `importlib` (existing) | stdlib | Dynamic macro factory resolution from `"module.path:Symbol"` strings | Already used in `_resolve_macro_factory`. |

### Supporting Libraries (New Dev-Only Additions)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| nbmake | >=1.5.3 | Execute Jupyter notebook tutorials as pytest tests | Add when tutorial notebooks are created; ensures `.ipynb` files run end-to-end without a live QM server |
| ipykernel | >=7.0.0a1 (already in dev deps) | Jupyter kernel for notebook authoring | Already in `pyproject.toml` dev group — no change needed |

**nbmake rationale:** The project already uses `ipykernel` in dev deps and has
example `.py` scripts in `examples/`. When tutorials are written as `.ipynb`
files, `nbmake` integrates with the existing `pytest` invocation (`pytest --nbmake docs/`)
so tutorial notebooks are validated in CI without a separate notebook testing framework.
This is the narrowest possible addition — a single dev-only package.

**Confidence:** MEDIUM. `nbmake` is the standard pytest-native notebook runner.
The alternative `nbval` requires `jupyter nbconvert` infrastructure and is more
fragile with dependency mocking. HIGH confidence that either works; MEDIUM that
`nbmake` is the right choice specifically for this repo's setup.

### Development Tools (No Changes Required)

| Tool | Current Version | Status |
|------|----------------|--------|
| ruff | 0.14.11 | Sufficient — 100-char line length, `select = ["E","F","W","I","UP","B","C4"]` |
| mypy | 1.19.1 | Sufficient — `ignore_missing_imports = true` handles qm-qua stubs |
| pylint | >=3.0 (from pyproject) | QUA plugin loaded — preserves boolean semantics |
| pytest | 8.4.2 / 9.0.1 | Sufficient |

---

## Installation

```bash
# No new runtime dependencies.

# Dev-only: add nbmake when tutorials are created as notebooks
uv add --dev nbmake
```

---

## Alternatives Considered

### Documentation Format: Jupyter Notebooks vs RST vs Markdown

**Recommendation: Jupyter notebooks (.ipynb) for tutorials, Markdown (.md) for API reference prose.**

| Format | Recommended | Alternative | When to Use Alternative |
|--------|-------------|-------------|------------------------|
| Jupyter notebooks | YES (tutorials) | Pure Python scripts (.py) | Scripts are fine if notebooks add no value — but customers expect runnable notebooks for quantum hardware libraries; the existing `examples/` dir already has `.py` scripts serving as developer docs, so notebooks fill a distinct customer-facing niche |
| Markdown prose | YES (quickstart README) | RST + Sphinx | Use Sphinx/RST only if a full hosted documentation site is scoped (it is NOT in this milestone) |
| RST + Sphinx | NO for this milestone | — | Sphinx requires a dedicated doc build pipeline; this milestone only needs a quickstart tutorial, not a full API site |

**Why notebooks beat pure .py for customer tutorials in this domain:**
- Customers use JupyterLab or VS Code notebooks as their primary interface to the QOP stack
- Notebooks allow mixing prose explaining the four macro customization workflows with executable cells that call `wire_machine_macros()`
- Output cells can show `machine.qubits["Q1"].macros` dict content, making the abstract dispatch chain concrete
- The `qua-platform` ecosystem (qualibrate, qua-libs) already delivers tutorials as notebooks

**Notebook execution strategy (no live hardware required):**
The macro system is designed so that `wire_machine_macros()` and `@quam_dataclass`
macro registration are pure Python — no QM server connection needed. Only
`macro.apply()` calls inside `with program():` blocks require a server.
Tutorial notebooks can demonstrate workflows 1-4 (use defaults, type-level overrides,
instance overrides, external macro package) entirely in pure Python, deferring
any `with program():` block to a clearly-labelled "hardware required" cell.

### Testing QUA Dispatch Chains Without a Live Server

**Recommendation: `unittest.mock.patch.object` (already in use) — no new tools.**

The existing test suite in `tests/builder/quantum_dots/test_macro_wiring.py` and
`tests/macros/test_macro_classes.py` demonstrates the established pattern:

```python
# Pattern already validated in test_macro_wiring.py
with patch.object(q1, "call_macro", return_value=None) as mock_call:
    q1.macros["x"].apply(angle=np.pi / 3)
mock_call.assert_called_once_with("xy_drive", angle=np.pi / 3, phase=0.0)

# Pattern for voltage-sequence dispatch
with patch.object(qd.voltage_sequence, "step_to_point") as mock_step:
    with qua.program() as prog:
        macro.apply()
    mock_step.assert_called_once()
```

This works because `qm.qua.program()` builds an IR graph without requiring a
server connection — the QUA DSL is a hosted embedded DSL that records operations.
Patching at the `voltage_sequence` method boundary tests macro dispatch logic
without involving the QUA compiler or OPX hardware.

**Why NOT qua-qsim (the AST-based simulator in `pyproject.toml`):**
`qua-qsim` is listed under `[dependency-groups.ast]` as an optional dev group.
It operates on the compiled QUA AST, not on the macro dispatch layer. For testing
that `QuantumDot.initialize()` dispatches to `InitializeStateMacro.apply()` which
calls `ramp_to_point()` — that's a Python-layer dispatch test, not a QUA program
semantics test. `qua-qsim` is appropriate for verifying timing and pulse-sequence
correctness, not for verifying macro registration and wiring behavior.

| Approach | Recommended | Why |
|----------|-------------|-----|
| `patch.object` on voltage_sequence methods | YES | Already in use; isolates macro dispatch from QUA IR; fast |
| `patch.object` on `call_macro` | YES | For testing delegation chains (XMacro → xy_drive) |
| `qua.program()` context manager | YES (where needed) | Open without server; tests macro.apply() runs without crashing |
| `qua-qsim` | NOT for this milestone | Overkill for macro registration tests; reserve for pulse-level validation |
| Live QM server (`@pytest.mark.server`) | NOT for unit tests | Already gated behind `server` marker; correct policy |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| New runtime dependencies | `QuantumDot`/`SensorDot`/`QuantumDotPair` already have `VoltageMacroMixin` and `MacroDispatchMixin` — catalog registration is 3 lines of Python using what exists | Nothing; extend `component_macro_catalog.py` directly |
| Sphinx + autodoc | Requires separate doc build pipeline; not in scope; adds maintenance burden | Markdown README + Jupyter notebook tutorial |
| `nbval` for notebook testing | Less maintained than `nbmake`; requires more infrastructure | `nbmake` (if notebooks are adopted) |
| Separate macro base class for voltage-only components | `QuamMacro` (not `QubitMacro`) is the correct base for `QuantumDot`/`SensorDot`/`QuantumDotPair` macros — `QubitMacro` assumes a `.qubit` parent link which these components do not have; state_macros.py already uses `QuamMacro` with `_owner_component()` for this reason | `QuamMacro` + `_owner_component()` pattern (already validated) |
| Dataclass inheritance from `QubitMacro` for QuantumDot macros | `QubitMacro` sets `self.qubit` as parent reference; `QuantumDot` components are not `Qubit` subclasses | Use `QuamMacro` directly, following the `InitializeStateMacro`/`MeasureStateMacro`/`EmptyStateMacro` pattern in `state_macros.py` |
| Global mutable state for macro defaults | Already avoided; `macro_registry.py` uses a module-level dict keyed by fully-qualified class name; this is the approved pattern | Continue using `register_component_macro_factories()` |

---

## Stack Patterns by Variant

**For QuantumDot / SensorDot catalog registration:**
- Add lazy imports for `QuantumDot`, `SensorDot` in `component_macro_catalog.py`
- Register `STATE_POINT_MACROS` (already defined in `state_macros.py`) for both types
- `SensorDot` inherits from `QuantumDot` — MRO-aware resolution means `QuantumDot`
  registration covers `SensorDot` automatically if registered first; register `SensorDot`
  separately only if it needs different defaults (it likely does not for state macros)
- `QuantumDot` does NOT have `xy` drive; do NOT register `XYDriveMacro` or any
  `_AxisRotationMacro` subclass for it — those require `qubit.xy` and `qubit.virtual_z()`

**For QuantumDotPair catalog registration:**
- `QuantumDotPair` already has `VoltageMacroMixin`; it needs state macros only
- Register `STATE_POINT_MACROS` (same as `QuantumDot`)
- Do NOT register two-qubit gate placeholders (CNOT/CZ/SWAP/iSWAP) — those belong
  to `LDQubitPair`, which has an `xy` drive on each constituent qubit

**For tutorial notebook structure:**
- One notebook covering all four workflows in sequence
- Cells that only require Python (no hardware): workflows 1, 2, 3, 4 definition
- Cells that require `with program():` (no server): show macro dispatch structure
- Cells clearly marked "requires live hardware": macro.apply() inside program blocks
- Use `LossDiVincenzoQuam` + the existing `conftest.py` fixture as the tutorial machine

**For XYDriveMacro / _AxisRotationMacro completeness check:**
- All classes in `SINGLE_QUBIT_MACROS` dict are already implemented in
  `single_qubit_macros.py` (verified by file inspection)
- `XMacro`, `YMacro`, `ZMacro`, all fixed-angle variants, `IdentityMacro` are present
- The chain `X180Macro → XMacro → XYDriveMacro` is complete and tested
- No new macro classes are needed; the gap is only in catalog registration

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| quam 0.5.0a2 | qm-qua 1.2.3.1 | Both are Quantum Machines packages; locked together in uv.lock — do not upgrade independently |
| Python 3.9–3.12 | All packages in lock | `tomllib` stdlib only in 3.11+; project uses it already, so Python >=3.11 is the practical minimum for the TOML profile feature |
| pytest 8.4.2 (py3.9) / 9.0.1 (py3.10+) | pytest-mock 3.15.1, pytest-cov 7.0.0 | Resolution markers in uv.lock handle this automatically |
| nbmake >=1.5.3 (if added) | pytest 9.x, ipykernel 7.x | nbmake depends on pytest and nbformat; ipykernel already in dev deps |

---

## Sources

- `pyproject.toml` (file inspection) — runtime dependencies, dev tools, Python version constraint
- `uv.lock` (file inspection) — exact locked versions for quam (0.5.0a2), qm-qua (1.2.3.1), pytest (8.4.2/9.0.1), pytest-mock (3.15.1), pytest-cov (7.0.0), ruff (0.14.11), mypy (1.19.1)
- `quam_builder/architecture/quantum_dots/operations/component_macro_catalog.py` — registration pattern, current coverage gap (QuantumDot/SensorDot/QuantumDotPair missing)
- `quam_builder/architecture/quantum_dots/operations/default_macros/single_qubit_macros.py` — all XY/axis/fixed-angle macros confirmed present and complete
- `quam_builder/architecture/quantum_dots/operations/default_macros/state_macros.py` — `STATE_POINT_MACROS` dict, `_owner_component()` pattern for non-Qubit components
- `quam_builder/architecture/quantum_dots/macro_engine/wiring.py` — `wire_machine_macros` API, TOML loading, MRO-aware dispatch
- `quam_builder/architecture/quantum_dots/components/quantum_dot.py` — `QuantumDot` class; no `xy` drive; voltage-only
- `quam_builder/architecture/quantum_dots/components/sensor_dot.py` — `SensorDot(QuantumDot)` inheritance
- `quam_builder/architecture/quantum_dots/components/quantum_dot_pair.py` — `QuantumDotPair(VoltageMacroMixin)` without qubit semantics
- `tests/builder/quantum_dots/test_macro_wiring.py` — established mock pattern for macro dispatch testing
- `tests/macros/test_macro_classes.py` — established `with qua.program()` + `patch.object(voltage_sequence)` pattern

---

*Stack research for: quam-builder v1.0 QD Operations milestone*
*Researched: 2026-03-03*
