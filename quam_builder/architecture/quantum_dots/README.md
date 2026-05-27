# Quantum-dot QuAM architecture

This package (`quam_builder.architecture.quantum_dots`) provides QuAM components, voltage-control tooling, default operations and macros, and wiring helpers for **quantum-dot and spin-qubit** processors.

It is aimed at:

- Labs **building a machine from connectivity specs** (recommended: [`quam_builder.builder.quantum_dots`](../../builder/quantum_dots/)).
- Experimentalists **moving from raw QUA** to a structured QuAM machine (components, named voltage points, macros, and `wire_machine_macros`).

You can use the **builder** to generate a full machine, or assemble **components piecemeal** when you need a custom topology. Child READMEs cover specific areas in depth; this document is the onboarding hub.

## Prerequisites

You should be familiar with:

- **[QUAM](https://qua-platform.github.io/quam/)** — machine components, serialization, and references.
- **[QUA](https://docs.quantum-machines.co/latest/)** — programs, sticky elements, and pulse play.
- **[qualang_tools](https://github.com/qua-platform/qualang-tools)** (optional but common) — connectivity / wiring helpers used by several examples and by `build_quam_wiring`.

This documentation stays **hardware-agnostic** (no specific OPX port lists here). Examples may assume LF-FEM or cluster settings; adapt ports and hosts to your setup.

## Package map

| Area | Location | Role |
|------|----------|------|
| Components | [`components/`](components/) | Primary QuAM dataclasses: dots, gates, readout, `QPU`, etc. |
| Voltage sequencing | [`voltage_sequence/`](voltage_sequence/) | `GateSet`, `VoltageSequence`, constants; see [voltage_sequence/README.md](voltage_sequence/README.md) for the full DC/virtual-gate guide |
| Virtual gates (compat) | [`virtual_gates/`](virtual_gates/) | Re-exports aligned with legacy import paths; prefer `components` for new code |
| Operations & defaults | [`operations/`](operations/) | Macro and pulse registries, canonical names, default macro classes — [operations/README.md](operations/README.md) |
| Macro engine | [`macro_engine/`](macro_engine/) | `wire_machine_macros`, TOML profiles, `ComponentOverrides` — entry in [`macro_engine/__init__.py`](macro_engine/__init__.py), implementation in [`macro_engine/wiring.py`](macro_engine/wiring.py) |
| QPU models | [`qpu/`](qpu/) | `BaseQuamQD` (dot-centric root); **Loss DiVincenzo spin stack** — [`qpu/README.md`](qpu/README.md) (`LossDiVincenzoQuam`, `LDQubit`, `LDQubitPair`, XY drives) |
| Examples | [`examples/`](examples/) | Runnable scripts and tutorial helpers |

## Start here

Read the sections below in order for your goal. All paths assume you will run QUA against a QuAM machine object (built or loaded).

### 1. Build the machine (recommended first step)

Use [`quam_builder.builder.quantum_dots`](../../builder/quantum_dots/) to materialize connectivity into a QuAM tree:

- **`build_quam`** — combined workflow when you have wiring + qubit/dot specs.
- **`build_base_quam`** — dot-centric layout (`BaseQuamQD`): virtual gate sets, dots, pairs, sensors, barriers.
- **`build_loss_divincenzo_quam`** — extends the dot layout with spin qubits (`LossDiVincenzoQuam`, `LDQubit`, pairs, XY drives).

Pair this with [`quam_builder.builder.qop_connectivity`](../../builder/qop_connectivity/) (`build_quam_wiring`) so logical elements map to controller ports. Builder entry points call **`wire_machine_macros`** so default macros and pulses exist on the loaded machine.

**Coming from QUA:** you replace ad-hoc channel dicts and copy-pasted pulse blocks with a single machine object, named voltage points, and `qubit.x180()`-style macros after wiring.

### 2. Understand the machine layout

After building (or loading a saved machine), the usual roots are:

| Root type | Use when |
|-----------|----------|
| **`BaseQuamQD`** | Calibrating **dots and gates** (plungers, barriers, sensors) without a full spin abstraction. |
| **`LossDiVincenzoQuam`** | Running **ESR/EDSR and two-qubit** experiments on top of the same dot connectivity. |

Key groupings: `virtual_gate_sets`, `voltage_sequences`, `quantum_dots`, `qubit_pairs`, `qubits` (spin stack only). Dots and qubits delegate voltage moves through **`VoltageSequence`** on the relevant gate set.

Details: [`qpu/README.md`](qpu/README.md).

### 3. DC gates and voltage sequences

For **sticky DC** control in QUA:

1. Define **`VoltageGate`** channels (with `half_max_square` operations).
2. Group them in a **`GateSet`** or **`VirtualGateSet`** (virtualization layers for tuning axes).
3. Inside a QUA program: `seq = gate_set.new_sequence()` then `step_to_voltages` / `ramp_to_point` / etc.

Default behaviour uses **`keep_levels=True`**: gate names you omit keep their last value (physical and virtual). Pass `keep_levels=False` when every call should treat omitted gates as 0 V. See [voltage_sequence/README.md](voltage_sequence/README.md).

**Coming from QUA:** you keep writing `program()` blocks, but voltage targets are absolute levels tracked per channel instead of manual delta pulses on each gate.

### 4. Macros, pulses, and overrides

Default **state** macros (`initialize`, `measure`, `empty`, `exchange`) and **gate** macros (`x180`, `cz`, …) are registered per component type under [`operations/`](operations/). At runtime, **`wire_machine_macros`** fills missing defaults and applies Python or TOML overrides.

Typical flow: build machine → `wire_machine_macros(machine)` (often already done in `load()` / builder) → call `qubit.initialize()` or `qubit.x180()` in QUA.

Override patterns (single macro, type-level, TOML profile): [operations/README.md](operations/README.md).

## Component inventory

**Machine root**

- **`QPU`** — Top-level quantum processing unit component.

**Voltage and gate control**

- **`VoltageGate`** — Baseband channel with `offset_parameter` and `attenuation` (extends `SingleChannel`) for OPX control plus optional external DC drivers.
- **`GateSet`**, **`VirtualGateSet`**, **`VirtualizationLayer`** — Group channels, named tuning points, and layered virtual-to-physical maps. Math and workflows: [voltage_sequence/README.md](voltage_sequence/README.md).
- **`GlobalGate`** — `VoltageGate` not tied to a `GateSet` (e.g. global back gate).
- **`VirtualDCSet`** — Python-side virtualization of external DC instruments (`offset_parameter`); shares layer concepts with `VirtualGateSet` but is not the QUA `VoltageSequence` path.
- **`VoltageSequence`** — QUA sequence helper for a `GateSet` / `VirtualGateSet` (level tracking, optional integrated-voltage compensation). See [voltage_sequence/README.md](voltage_sequence/README.md).

**Readout and transport**

- **`ReadoutResonator`**, **`ReadoutTransport`**, **`Reservoir`** — Resonator and transport/reservoir constructs for readout.

**Dot topology and coupling**

- **`QuantumDot`** — Single dot, tied to a `VoltageGate` and the machine’s `VirtualGateSet`.
- **`QuantumDotPair`** — Two dots plus shared barrier control.
- **`SensorDot`** — Sensor dot for SET-style readout.

**Hardware helpers**

- **`DacSpec`**, **`QdacSpec`** — DAC channel metadata on `VoltageGate` ([`dac_spec.py`](components/dac_spec.py)).

**Mixins and pulses**

- **`mixins/`** — `VoltageMacroMixin`, voltage-point helpers, macro dispatch shared by several components.
- **`pulses.py`** — Pulse helpers; default pulse factories are registered with macros in `operations/`.

**Spin qubits (Loss DiVincenzo)**

- **`LossDiVincenzoQuam`**, **`LDQubit`**, **`LDQubitPair`**, **XY drives** — See [`qpu/README.md`](qpu/README.md).

## Voltage sequencing and virtualization

`GateSet` and `VoltageSequence` coordinate sticky channels in QUA, track absolute levels (and optional integrated voltage for compensation), and apply named tuning-point macros. `VirtualGateSet` adds `VirtualizationLayer` matrices so experiments can work in virtual gate space.

Requirements and behaviour:

- Channels must be **sticky** for correct holding and `ramp_to_zero`.
- By default, **`keep_levels=True`** on `new_sequence()`: omitted physical and virtual gate names **keep their last value**; use `keep_levels=False` or explicit `0.0` to clear contributions.
- Full workflows, API detail, and mathematics: **[voltage_sequence/README.md](voltage_sequence/README.md)**.

## Operations and macros

Canonical names (`initialize`, `measure`, `x180`, `cz`, …) live in [`operations/names.py`](operations/names.py). Default macro classes and per-component maps are under [`operations/default_macros/`](operations/default_macros/).

| Topic | Document |
|-------|----------|
| Macro tables, invocation (`q.x180()` vs registry), overrides | [operations/README.md](operations/README.md) |
| Spin-qubit component layout | [qpu/README.md](qpu/README.md) |

## Macro engine and machine wiring

**`wire_machine_macros`** ([`macro_engine/wiring.py`](macro_engine/wiring.py)) materializes missing default macros and pulses and merges **`ComponentOverrides`** from Python or TOML (`load_macro_profile`). It runs during component setup, **builder** entry points, and `BaseQuamQD` / `LossDiVincenzoQuam` **`load()`** so serialized machines stay consistent.

Helper entry points: [`macro_engine/__init__.py`](macro_engine/__init__.py) (`macro`, `pulse`, `overrides`, `disabled`). Details: [operations/README.md](operations/README.md).

## Building and loading QuAM machines

**Preferred path:** [`quam_builder.builder.quantum_dots`](../../builder/quantum_dots/)

| Function | Produces |
|----------|----------|
| `build_quam` | Full machine from connectivity + specs (common entry point). |
| `build_base_quam` | `BaseQuamQD` — dots, gate sets, sensors, pairs. |
| `build_loss_divincenzo_quam` | `LossDiVincenzoQuam` — adds qubits, pairs, MW/XY wiring. |

Staged builders (`build_qpu_stage1`, `build_qpu_stage2`) and utilities live in the same package. Combine with **`build_quam_wiring`** from [`quam_builder.builder.qop_connectivity`](../../builder/qop_connectivity/) for port mapping.

After build: `machine.save()` / `machine.load()`; spin roots may upgrade from `BaseQuamQD` on load and re-run wiring.

For **manual** assembly (custom topology without the builder), follow the workflow described in [`quam_qd_example.py`](examples/quam_qd_example.py) and [`quam_ld_example.py`](examples/quam_ld_example.py) docstrings — register channels, `create_virtual_gate_set`, dots, then qubits.

## Examples

Scripts live under [`examples/`](examples/). **Start with the shared machine builder**, then run scripts that import it:

| Script | What it demonstrates |
|--------|----------------------|
| [`tutorial_machine.py`](examples/tutorial_machine.py) | **`build_tutorial_machine()`** — minimal `LossDiVincenzoQuam` (dots, pair, qubits, virtual gate set, voltage points for state macros). Intended as the shared machine for tutorials; does not call `wire_machine_macros` (callers wire macros themselves). |
| [`default_macro_defaults_example.py`](examples/default_macro_defaults_example.py) | Wire defaults only, parameterize built-in macros/pulses, run QUA using `initialize` / `x180`. |
| [`full_workflow_example.py`](examples/full_workflow_example.py) | Builder + `wire_machine_macros`, pulse/macro overrides, DRAG swap (end-to-end spin workflow). |
| [`quam_qd_generator_example.py`](examples/quam_qd_generator_example.py) | **Builder-first** generator path for a dot + LD qubit machine. |
| [`virtual_gate_set_example.py`](examples/virtual_gate_set_example.py) | `VirtualGateSet` layers and `resolve_voltages` (includes rectangular-matrix check). |
| [`wiring_example.py`](examples/wiring_example.py) | Connectivity / `build_quam_wiring` with quantum-dot builders. |

**More scripts** in [`examples/`](examples/) (overrides-only, Rabi–Chevron, external macro packages, `VirtualDCSet`, pulse overrides, etc.) — read each file’s module docstring for scope and prerequisites.

## Import cheat sheet

```python
from quam_builder.architecture.quantum_dots.components import (
    VoltageGate,
    GateSet,
    VirtualGateSet,
    QuantumDot,
    QPU,
)
from quam_builder.architecture.quantum_dots.macro_engine import (
    wire_machine_macros,
    overrides,
    macro,
    ComponentOverrides,
)
from quam_builder.builder.quantum_dots import build_quam, build_loss_divincenzo_quam
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD, LossDiVincenzoQuam
```

For `LDQubit`, `LDQubitPair`, and XY drive types, see **[`qpu/README.md`](qpu/README.md)**. For DC sequencing detail, see **[`voltage_sequence/README.md`](voltage_sequence/README.md)**.
