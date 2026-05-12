# Guides

Narrative documentation organized by qubit architecture and tooling. Each guide is sourced from a `README.md` in the codebase, so the guides stay in sync with the source of truth.

## Architecture Guides

- **[Superconducting](superconducting.md)** — Transmon-based QPU components, qubit types (fixed-frequency, flux-tunable), readout resonators, drive lines, couplers, and qubit pair structures.
- **[Quantum Dots](quantum_dots.md)** — `VoltageGate`, `GateSet`, `VoltageSequence`, `VirtualGateSet`, and `VirtualizationLayer` for orchestrating DC voltage control of spin qubits in QUA.

## Tooling Guides

- **[Voltage Sequence](voltage_sequence.md)** — Tooling for sequencing voltage operations across channels with state tracking.
- **[Pylint QUA Plugin](pylint_plugin.md)** — A custom pylint plugin that suppresses false positives in QUA contexts (e.g., `with` statements, scope detection).

!!! tip "Looking for code-level reference?"
    Visit the [API Reference](../api/index.md) section, which is auto-generated from the source code's docstrings and type hints.
