# quam-builder

## What This Is

`quam-builder` is a Python library for programmatically constructing QUAM (Quantum Abstract Machine) configurations for Quantum Machines' Quantum Orchestration Platform (QOP). It provides modular architecture definitions, QOP wiring generation, and builder functions for multiple qubit types. It is customer-facing and used alongside QUAlibrate and qua-libs.

## Core Value

Customers can build complete, correct QUAM configurations without manually managing low-level hardware wiring — and customize gate behavior without forking the library.

## Requirements

### Validated

<!-- Shipped and confirmed valuable across v0.1.0–v0.2.0 -->

- ✓ Superconducting qubit architecture (FixedFrequency and FluxTunable transmons, readout resonators, drive/flux lines, couplers) — v0.1.0
- ✓ QOP wiring generation (build_quam_wiring, port assignment, connectivity mapping) — v0.1.0
- ✓ NV center architecture (full QPU, qubit, components) — v0.2.0
- ✓ Quantum dots architecture (VoltageGate, GateSet, VirtualGateSet, VoltageSequence, QuantumDot, QuantumDotPair, SensorDot, LDQubit, LDQubitPair) — v0.2.0
- ✓ Power tools for MW/IQ channel output management — v0.1.2

### Active

<!-- Current scope: v1.0 — QD Operations milestone -->

- [ ] QuantumDot, SensorDot, and QuantumDotPair registered with default state macros
- [ ] All single-qubit macro wrappers (XMacro, YMacro, ZMacro, and fixed-angle variants) fully implemented
- [ ] OperationsRegistry role clarified and consistent with wire_machine_macros system
- [ ] Customer-facing documentation and tutorial covering all four macro customization workflows
- [ ] Test coverage for QuantumDot/SensorDot/QuantumDotPair macro defaults

### Out of Scope

- Superconducting qubit macro system — independent architecture, not in this milestone
- NV center macro system — not yet scoped
- Neutral atoms architecture — not yet started
- Working QUA implementations for two-qubit gates (cnot, cz, swap, iswap) — explicit placeholders until calibration logic is supplied by users

## Context

The `feature/qd_default_operations` branch introduces a config-driven macro system for quantum dots:

- `wire_machine_macros(machine, macro_profile_path=..., macro_overrides=...)` — runtime wiring API
- TOML profile + Python dict overrides, supporting component-type and instance-level targeting
- Macro registry with MRO-aware resolution (`macro_registry.py`)
- Canonical enum-backed names (`names.py`)
- Real implementations for state macros and XYDriveMacro
- Component catalog currently covers `QPU`, `LDQubit`, `LDQubitPair` only

`QuantumDot`, `SensorDot`, and `QuantumDotPair` inherit `VoltageMacroMixin` but are not yet in the component catalog — they only receive utility macros (align, wait).

The four customer workflows this milestone targets:
1. Use defaults out of the box
2. Edit defaults globally (component-type level)
3. Override per component (instance level)
4. Bring an external macro package

## Constraints

- **Architecture**: QD macro system is independent of superconducting — do not couple them
- **Serialization**: Macro objects/fields in `component.macros` are part of QuAM state — all macro classes must be serializable via `@quam_dataclass`
- **QUA semantics**: No simplification of boolean expressions inside `with program():` blocks; preserve explicit type declarations; timing must align to 4ns clock cycles
- **Compatibility**: Post-build dict mutation (`component.macros["x180"] = MyMacro()`) must remain a valid escape hatch

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Config-driven defaults via `wire_machine_macros` | Avoids global mutable state; testable; no subclassing required for common cases | — Pending |
| Macro registry decoupled from component classes | Keeps macro wiring explicit and local to architecture package; survives upstream pulls | — Pending |
| TOML + Python runtime overrides merged | TOML for stable lab defaults, Python for session-specific tweaks | — Pending |
| Enum-backed canonical names | Prevents string typos; enables IDE autocomplete on macro names | — Pending |
| Explicit NotImplementedError placeholders for 2Q gates | Forces users to supply calibrated logic; avoids silent no-ops | — Pending |

---
*Last updated: 2026-03-03 — Milestone v1.0 QD Operations started*
