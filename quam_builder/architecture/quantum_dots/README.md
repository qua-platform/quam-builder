# Quantum-dot QuAM architecture

This package (`quam_builder.architecture.quantum_dots`) provides QuAM components, voltage-control tooling, default operations and macros, and wiring helpers for quantum-dot and spin-qubit style processors. It is meant to be used together with the builder in [`quam_builder.builder.quantum_dots`](../../builder/quantum_dots/) when generating full machines, or piecemeal when defining custom topologies.

## Package map

| Area | Location | Role |
|------|----------|------|
| Components | [`components/`](components/) | Primary QuAM dataclasses: dots, gates, readout, `QPU`, etc. |
| Voltage sequencing | [`voltage_sequence/`](voltage_sequence/) | `GateSet`, `VoltageSequence`, constants; see [voltage_sequence/README.md](voltage_sequence/README.md) for the full DC/virtual-gate guide |
| Virtual gates (compat) | [`virtual_gates/`](virtual_gates/) | Re-exports aligned with legacy import paths; prefer `components` for new code |
| Operations & defaults | [`operations/`](operations/) | Macro and pulse registries, canonical names, default macro classes — [operations/README.md](operations/README.md) |
| Macro engine | [`macro_engine/`](macro_engine/) | `wire_machine_macros`, TOML profiles, `ComponentOverrides` — entry in [`macro_engine/__init__.py`](macro_engine/__init__.py), implementation in [`macro_engine/wiring.py`](macro_engine/wiring.py) |
| QPU models | [`qpu/`](qpu/) | `BaseQuamQD` (dot-centric root); **Loss DiVincenzo spin stack** — [`qpu/README.md`](qpu/README.md) (`LossDiVincenzoQuam`, `LDQubit`, `LDQubitPair`, XY drives) |
| Examples | [`examples/`](examples/) | Runnable scripts |

Resolution math for virtual gates and full `VoltageSequence` behaviour are documented in [voltage_sequence/README.md](voltage_sequence/README.md).

## Component inventory

Exports are centered on [`components/__init__.py`](components/__init__.py). Typical roles:

**Voltage and gate control**

- **`VoltageGate`** — Quantum-dot-oriented channel with `offset_parameter` and `attenuation` (extends `SingleChannel`).
- **`GateSet`** — Groups channels, named tuning points (`VoltageTuningPoint` / `add_point`), and `new_sequence()`.
- **`VirtualGateSet`**, **`VirtualizationLayer`** — Stacked linear maps from virtual to physical (or lower virtual) gates; see [voltage_sequence/README.md](voltage_sequence/README.md).
- **`GlobalGate`**, **`VirtualDcSet`** — Additional abstractions for shared or virtual DC control contexts.
- **`BarrierGate`** — Barrier electrode between dots.

**Dot topology and coupling**

- **`QuantumDot`** — Single dot, tied to a `VoltageGate` and the machine’s voltage sequence.
- **`QuantumDotPair`** — Two dots plus barrier; can extend detuning virtualization on the pair’s `VirtualGateSet`.
- **`SensorDot`** — Sensor dot for readout-style layouts.

**Readout and transport**

- **`ReadoutResonator`**, **`ReadoutTransport`**, **`Reservoir`** — Resonator and transport/reservoir constructs for multi-dot layouts.

**Machine root**

- **`QPU`** — Top-level quantum processing unit component used in generated layouts; concrete loaded machines often use **`BaseQuamQD`** from [`qpu/`](qpu/). For **Loss DiVincenzo spin qubits**, XY drives, and `LDQubit` / `LDQubitPair`, see **[`qpu/README.md`](qpu/README.md)**.

**Hardware helpers**

- **`DacSpec`**, **`QdacSpec`** — DAC channel metadata parented under `VoltageGate` ([`dac_spec.py`](components/dac_spec.py)).

**Mixins and pulses**

- **`mixins/`** — `VoltageMacroMixin`, voltage-point helpers, macro dispatch (`MacroDispatchMixin` patterns) shared by several components.
- **`pulses.py`** — Pulse helpers used with dot channels; default pulse factories are registered alongside macros in `operations/`.

## Voltage sequencing and virtualization

`GateSet` and **`VoltageSequence`** coordinate sticky DC channels in QUA, track absolute levels (and optional integrated voltage for compensation), and apply named macros. **`VirtualGateSet`** adds layered matrices (`VirtualizationLayer`) so experiments can work in virtual gate space. Channels used with these tools should be **sticky**; zeroing semantics for omitted gates are important when mixing virtual and physical control.

Full workflows, API tables, mathematics, rectangular-matrix mode, and end-to-end examples: **[voltage_sequence/README.md](voltage_sequence/README.md)**.

## Operations and macros

Canonical voltage-point names (`initialize`, `measure`, `empty`, `exchange`) and macro names (`SingleQubitMacroName`, `TwoQubitMacroName`, aliases) live in [`operations/names.py`](operations/names.py). Default macro classes and per-component maps are under [`operations/default_macros/`](operations/default_macros/); registries wire defaults for `QPU`, dot-level components, and (for spin stacks) `LDQubit` / `LDQubitPair`. Spin-qubit-oriented overview: **[`qpu/README.md`](qpu/README.md)**; full macro tables and overrides: **[operations/README.md](operations/README.md)**.

## Macro engine and machine wiring

At runtime, **`wire_machine_macros`** (see [`macro_engine/wiring.py`](macro_engine/wiring.py)) materializes missing default macros and pulses and applies **`ComponentOverrides`** from Python or TOML (`load_macro_profile`). Wiring runs during component setup, builder entry points, and QPU `load` paths so serialized machines stay consistent. Details of override entries (`macro`, `pulse`, `disabled`, `overrides`) are summarized in [`macro_engine/__init__.py`](macro_engine/__init__.py) and expanded in [operations/README.md](operations/README.md).

## Building and loading QuAM machines

Generated quantum-dot machines are produced by the builder package [`quam_builder.builder.quantum_dots`](../../builder/quantum_dots/) (`build_base_quam`, `build_loss_divincenzo_quam`, `build_quam`, and staged builders). Use that package’s docstrings and tests for build-time behaviour.

## Examples and tests

**Examples** (under [`examples/`](examples/)):

- [`virtual_gate_set_example.py`](examples/virtual_gate_set_example.py) — Virtual gate set usage
- [`full_workflow_example.py`](examples/full_workflow_example.py) — Broader workflow
- [`quam_ld_example.py`](examples/quam_ld_example.py), [`quam_ld_generator_example.py`](examples/quam_ld_generator_example.py) — Loss DiVincenzo machines (see [`qpu/README.md`](qpu/README.md))
- [`default_macro_overrides_example.py`](examples/default_macro_overrides_example.py), [`pulse_overrides_example.py`](examples/pulse_overrides_example.py) — Overrides
- [`wiring_example.py`](examples/wiring_example.py) — Macro wiring

**Tests**: [`tests/architecture/quantum_dots/`](../../../tests/architecture/quantum_dots/) — includes `components/`, `voltage_sequence/`, `virtual_gates/`, and `operations/` suites (for example rectangular virtual-gate round-trip coverage in `components/test_rectangular_virtual_gate_set.py`).

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
from quam_builder.architecture.quantum_dots.qpu import BaseQuamQD
```

For `LossDiVincenzoQuam`, `LDQubit`, `LDQubitPair`, and XY drive types, see **[`qpu/README.md`](qpu/README.md)**.

The top-level package re-exports `components`, `macro_engine`, `operations`, `qpu`, `qubit`, and `qubit_pair` ([`__init__.py`](__init__.py)); `examples` are also exported for convenience.
