# Phase 4: Customer Documentation — Research

**Goal:** A new lab customer can discover and use all four macro customization workflows from the tutorial alone, without reading library source code.

**Requirements:** DOCS-01, DOCS-02

---

## Executive Summary

This research answers: **What do I need to know to PLAN Phase 4 well?**

1. **Location:** No `tutorials/` or `docs/` directory exists. Create `tutorials/` at repo root for the notebook. Put the DOCS-02 script in `quam_builder/architecture/quantum_dots/examples/external_macro_package_example.py`.
2. **Without QM hardware:** `qua.program()`, `wire_machine_macros()`, and `component.macros[...].apply()` all work without a QOP connection. Building a QUA program constructs IR only. Existing `default_macro_*` examples already demonstrate this.
3. **Four workflows:** Mapped to concrete code with correct component paths and override shapes.
4. **@quam_dataclass:** Non-decorated macro classes cannot round-trip through `machine.save()`/`load()`. Demonstrate via save/load failure or silent state loss.
5. **DOCS-02 script:** Must show a self-contained, importable macro class in a separate module, passed via `macro_overrides`.
6. **Component types:** Success criteria require `QuantumDot`, `QuantumDotPair`, `SensorDot`. Use `qd_machine`-style fixture or `LossDiVincenzoQuam` with full registration.

---

## 1. Where Should the Tutorial Live?

- **`tutorials/`** — Does not exist. Create `tutorials/macro_customization.ipynb` at repo root. Add `tutorials/README.md` with intro and link from main README.
- **`docs/`** — Does not exist. Alternative: `docs/tutorials/` if a larger docs tree is preferred.
- **`examples/`** — Exists at `quam_builder/architecture/quantum_dots/examples/`. Put DOCS-02 script here: `external_macro_package_example.py`. README already references `default_macro_overrides_example.py` and `default_macro_defaults_example.py`.

---

## 2. What Does "Without QM Hardware" Mean Technically?

### What Works Without a QOP

- Machine construction, `wire_machine_macros(machine)`.
- `component.macros["name"].apply()` inside `qua.program()` — builds QUA IR in memory.
- `qua.program()` — constructs program AST; no network calls.
- `machine.save()` / `machine.load()` — file I/O only.

### What Requires QM Hardware

- `qm.open()`, `qm.run()`, `machine.connect()`.

### Evidence

`default_macro_overrides_example.py` builds a QUA program and returns it without calling `qm.run()`. The script exits after printing "Built QUA program successfully...". Same pattern in `default_macro_defaults_example.py`.

## 3. The Four Workflows in Practice

### Workflow 1: Use Defaults Out of the Box

```python
wire_machine_macros(machine)  # No profile, no overrides
```

Preconditions: Machine has populated collections; state macros need voltage points (e.g. `qubit.with_step_point("initialize", {...}, duration=200)`).

### Workflow 2: Type-Level Override

```python
wire_machine_macros(machine, macro_overrides={
    "component_types": {
        "QuantumDot": {"macros": {"initialize": {"factory": CustomInitMacro, "params": {"ramp_duration": 64}}}},
    }
}, strict=True)
```

Keys: Short class name or FQN. Affects all instances of that type.

### Workflow 3: Instance-Level Override

```python
wire_machine_macros(machine, macro_overrides={
    "instances": {
        "quantum_dots.dot_1": {"macros": {"initialize": {"factory": MyInitMacro}}},
        "qubits.q1": {"macros": {"x180": {"factory": TunedX180Macro}}},
    }
}, strict=True)
```

Paths: `<collection>.<component_id>`. Collections: `quantum_dots`, `sensor_dots`, `quantum_dot_pairs`, `qubits`, `qubit_pairs`, `qpu`, `barrier_gates`, `global_gates`.

### Workflow 4: External Macro Package

External package defines `build_macro_overrides()`; experiment calls:

```python
from my_lab_qd_macros.catalog import build_macro_overrides
wire_machine_macros(machine, macro_overrides=build_macro_overrides(), strict=True)
```

See `operations/README.md` lines 251-320 for full example. All custom macro classes must use `@quam_dataclass`.

---

## 4. @quam_dataclass Constraint

Non-decorated macro classes cannot round-trip through save()/load(). Demonstrate: (1) side-by-side BadMacro vs GoodMacro; (2) assign non-decorated macro, call machine.save() — expect failure or state loss; (3) same with @quam_dataclass — assert survival.

---

## 5. DOCS-02 Script Scope

Script must show: separate module with importable macro class, build_macro_overrides() function, passed to wire_machine_macros(). Suggested: examples/external_macro_package_example.py + examples/external_macro_demo/ subpackage.

---

## 6. Component Types

QuantumDot: initialize, measure, empty. QuantumDotPair: same. SensorDot: measure only. Use qd_machine-style LossDiVincenzoQuam build (conftest.py). Paths: quantum_dots.id, quantum_dot_pairs.id, sensor_dots.id.

---

## 7. Validation Architecture

Notebook: Run all cells; no errors. Optional assert macro bindings. Future: nbmake + pytest --nbmake tutorials/.
Script: python -m ...external_macro_package_example exits 0. Pytest test that calls main.
Checklist: notebook cell-by-cell OK, script exits 0, correct component types, @quam_dataclass shown, no qm.open/run/connect.

---

## 8. References

.planning/REQUIREMENTS.md, operations/README.md, macro_engine/wiring.py, default_macro_*.py examples, PITFALLS.md, conftest.py qd_machine, test_macro_persistence.py, component_macro_catalog.py.

---

## RESEARCH COMPLETE
