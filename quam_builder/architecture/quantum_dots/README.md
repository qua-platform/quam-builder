# Quantum-dot QuAM architecture

This package (`quam_builder.architecture.quantum_dots`) provides QuAM components, voltage-control tooling, default operations and macros, and wiring helpers for **quantum-dot and spin-qubit** processors.

It is aimed at:

- Labs **building a machine from connectivity specs** (recommended: [`quam_builder.builder.quantum_dots`](../../builder/quantum_dots/)).
- Experimentalists **moving from raw QUA** to a structured QuAM machine (components, named voltage points, macros, and `wire_machine_macros`).

You can use the **builder** to generate a full machine, or assemble **components piecemeal** when you need a custom topology. Child READMEs cover specific areas in depth; this document is the onboarding hub.

## Why this package

Spin-qubit experiments combine **sticky DC gate control**, **microwave drive**, and **readout** in one QUA program. Without structure, that usually means ad-hoc channel dicts, copy-pasted pulse blocks, and manual tracking of absolute gate voltages across ramps.

This package replaces that with a **serialized QuAM machine**: named voltage points, default macros, and wiring helpers so experiments read like `qubit.initialize()` / `qubit.x180()` instead of low-level `play`/`ramp` on every gate.

**Before (raw QUA sketch):**

```python
# Manual delta pulses; easy to lose track of absolute levels with sticky elements
with program() as prog:
    play("half_max_square", "plunger_1", amplitude_scale=0.12)
    wait(1000, "plunger_1")
    play("half_max_square", "plunger_2", amplitude_scale=-0.05)
    # Separate XY pulse block, timing left to the user
    play("gaussian_x180", "q1_xy", amplitude_scale=0.8)
```

**After (QuAM + macros):**

```python
from quam_builder.architecture.quantum_dots.examples.tutorial_machine import (
    build_tutorial_machine,
)

machine = build_tutorial_machine() 
q1 = machine.qubits["q1"]

with program() as prog:
    q1.initialize()          
    q1.x180()                
    q1.measure()             
```

Macros use the machine voltage sequence internally.

See [Start here](#start-here) for the full build workflow.

## What you get

- **Voltage sequencing** — `GateSet` / `VoltageSequence` with absolute level tracking (`keep_levels`) and optional integrated-voltage compensation for AC-coupled lines.
- **Virtual gate layers** — `VirtualGateSet` / `VirtualizationLayer` for abstract tuning axes (detuning, barrier coupling, hierarchical coarse/fine control).
- **Sticky DC support** — `VoltageGate` channels with `half_max_square` operations and `ramp_to_zero` semantics.
- **Default macros and pulses** — canonical names (`initialize`, `x180`, `cz`, …) wired by `wire_machine_macros`, overridable per lab or per qubit.
- **Spin-qubit stack** — `LossDiVincenzoQuam`, `LDQubit`, `LDQubitPair`, and XY drive variants (baseband / IQ / MW).
- **Readout components** — RF resonator and transport paths on `SensorDot`; PSB macros with thresholds and projectors.
- **Builder and wiring** — `build_quam`, `build_loss_divincenzo_quam`, and `build_quam_wiring` to materialize connectivity into a QuAM tree.
- **External DC virtualization** — `VirtualDCSet` for QCoDeS/QDAC-style instruments (Python-side, not QUA sequences).

## Prerequisites

You should be familiar with:

- **[QUA](https://docs.quantum-machines.co/latest/)** — programs, sticky elements, and pulse play.
- **[QUAM](https://qua-platform.github.io/quam/)** — machine components, serialization, and references.
- **[qualang_tools](https://github.com/qua-platform/py-qua-tools)** (optional but common) — connectivity / wiring helpers used by several examples and by `build_quam_wiring`.

This documentation stays **hardware-agnostic** (no specific OPX port lists here). Examples may assume LF-FEM or cluster settings; adapt ports and hosts to your setup.

## Package map

| Area | Location | Role |
|------|----------|------|
| Components | [`components/`](components/) | Hardware QuAM dataclasses: dots, gates, readout, XY drives, pulses — [components/README.md](components/README.md) |
| Voltage sequencing and Virtual gates | [`voltage_sequence/`](voltage_sequence/), [`virtual_gates/`](virtual_gates/) | Shared control and virtual-gate layers — [voltage_sequence/README.md](voltage_sequence/README.md) |
| Operations & defaults | [`operations/`](operations/) | Macro and pulse registries, canonical names, default macro classes — [operations/README.md](operations/README.md) |
| QPU models | [`qpu/`](qpu/) | `BaseQuamQD` (dot-centric root); **Loss DiVincenzo spin stack** — [`qpu/README.md`](qpu/README.md) (`LossDiVincenzoQuam`, `LDQubit`, `LDQubitPair`, XY drives) |
| Examples | [`examples/`](examples/) | Runnable scripts and tutorial helpers |

## Start here

First build a machine using the necessary components for your experimental setup.

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

### 3. Gates and voltage sequences

For **sticky** control in QUA:

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
- **`VirtualDCSet`** — Python-side virtualization of external DC instruments (`offset_parameter`); shares layer concepts with `VirtualGateSet` but is not used in `VoltageSequence`. See [voltage_sequence/README.md](voltage_sequence/README.md#10-virtualdcset-external-dc-instruments).
- **`VoltageSequence`** — QUA sequence helper for a `GateSet` / `VirtualGateSet` (level tracking, optional integrated-voltage compensation). See [voltage_sequence/README.md](voltage_sequence/README.md).

**Readout and transport**

- **`ReadoutResonator`**, **`ReadoutTransport`**, **`Reservoir`** — Resonator and transport/reservoir constructs for readout. Setup workflows: [components/README.md](components/README.md).

**Dot topology and coupling**

- **`QuantumDot`** — Single dot, tied to a `VoltageGate` or `VirtualGate` and the machine’s `VirtualGateSet`.
- **`QuantumDotPair`** — Two dots plus shared barrier control.
- **`SensorDot`** — Sensor dot for SET-style readout.

**Hardware helpers**

- **`DacSpec`**, **`QdacSpec`** — DAC channel metadata on `VoltageGate` ([`dac_spec.py`](components/dac_spec.py)).

**Pulses**

- **`pulses.py`** — Scalable pulse envelopes (Gaussian, Kaiser, Hermite, DRAG, …); default factories registered with macros in `operations/`. See [components/README.md](components/README.md).

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
| Spin-qubit component layout, IQ/MW setup, machine settings | [qpu/README.md](qpu/README.md) |
| Readout, transport, custom pulses, windowing | [components/README.md](components/README.md) |
| DC sequencing, detuning axis, timing limits | [voltage_sequence/README.md](voltage_sequence/README.md) |

## Macro engine and machine wiring

**`wire_machine_macros`** ([`macro_engine/wiring.py`](macro_engine/wiring.py)) materializes missing default macros and pulses and merges **`ComponentOverrides`** from Python or TOML (`load_macro_profile`). It runs during component setup, **builder** entry points, and `BaseQuamQD` / `LossDiVincenzoQuam` **`load()`** so serialized machines stay consistent.

<!-- Helper entry points: [`macro_engine/__init__.py`](macro_engine/__init__.py) (`macro`, `pulse`, `overrides`, `disabled`). Details: [operations/README.md](operations/README.md). -->

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
| [`tutorial_machine.py`](examples/tutorial_machine.py) | **`build_tutorial_machine()`** — minimal `LossDiVincenzoQuam` (dots, pair, qubits, virtual gate set, voltage points for state macros). Comes pre-wired with default macros and pulses via `build_quam`; the tutorial notebook re-calls `wire_machine_macros` for customization. |
| [`macro_defaults_example.py`](examples/macro_defaults_example.py) | Wire defaults only, parameterize built-in macros/pulses, run QUA using `initialize` / `x180`. |
| [`full_workflow_example.py`](examples/full_workflow_example.py) | Builder + `wire_machine_macros`, pulse/macro overrides, Kaiser pulse-family swap (end-to-end spin workflow). |
| [`quam_qd_generator_example.py`](examples/quam_qd_generator_example.py) | **Builder-first** generator path for a dot + LD qubit machine. |
| [`quam_qd_example.py`](examples/quam_qd_example.py) | **Manual assembly** of `BaseQuamQD`: virtual gate set, detuning axes, cross-compensation. |
| [`quam_ld_example.py`](examples/quam_ld_example.py) | Manual assembly of `LossDiVincenzoQuam` with qubits and XY drives. |
| [`virtual_gate_set_example.py`](examples/virtual_gate_set_example.py) | `VirtualGateSet` layers and `resolve_voltages` (includes rectangular-matrix check). |
| [`virtual_dc_set_example.py`](examples/virtual_dc_set_example.py) | `VirtualDCSet` layers driving external DC via `offset_parameter`. |
| [`voltage_balanced_macros_example.py`](examples/voltage_balanced_macros_example.py) | `VoltageBalancedMacroCatalog` for AC-coupled lines (zero net integral). |
| [`dcz_macro_example.py`](examples/dcz_macro_example.py) | Detuning-based two-qubit CZ (`BalancedDCz2QMacro`) with cloud simulation. |
| [`wiring_example.py`](examples/wiring_example.py) | Connectivity / `build_quam_wiring` with quantum-dot builders. |
| [`rabi_chevron.py`](examples/rabi_chevron.py) | Rabi–Chevron on MW-FEM with RF resonator readout. |
| [`rabi_chevron_transport.py`](examples/rabi_chevron_transport.py) | Same experiment using transport (DC) readout instead of resonator. |
| [`pulse_overrides_example.py`](examples/pulse_overrides_example.py) | Custom pulse shapes and amplitude overrides on XY channels. |
| [`macro_overrides_example.py`](examples/macro_overrides_example.py) | Catalog and instance macro overrides. |
| [`external_macro_package_example.py`](examples/external_macro_package_example.py) | Lab-owned macro package pattern. |
| [`qm_example.py`](examples/qm_example.py) | Full QM workflow with balanced macro catalog. |

**More scripts** in [`examples/`](examples/) (`mwe_sensor_resonator_same_port.py`, etc.) — read each file's module docstring for scope and prerequisites.

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

For `LDQubit`, `LDQubitPair`, and XY drive types, see **[`qpu/README.md`](qpu/README.md)**. For DC sequencing detail, see **[`voltage_sequence/README.md`](voltage_sequence/README.md)**. For readout and pulse shapes, see **[`components/README.md`](components/README.md)**.
