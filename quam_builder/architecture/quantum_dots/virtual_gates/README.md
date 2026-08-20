# Virtual gates

Virtual gate control is documented in the main DC / virtualization guide:

- **[voltage_sequence/README.md](../voltage_sequence/README.md)** — full API for `VirtualGateSet`, `VirtualizationLayer`, `VoltageSequence`, and `keep_levels` semantics (§6–7).
- **[§9 — Exchange-only detuning axis](../voltage_sequence/README.md#9-exchange-only-qubits-detuning-axis)** — map virtual detuning ε onto plunger gates for exchange-only qubits.
- **[§10 — VirtualDCSet](../voltage_sequence/README.md#10-virtualdcset-external-dc-instruments)** — Python-side virtualization for external DAC instruments.

## Quick links

| Topic | Section |
|-------|---------|
| Layer stacking and matrix math | [voltage_sequence §6–7](../voltage_sequence/README.md#6-virtualgateset) |
| Rectangular matrices / pseudo-inverse | [voltage_sequence §7.5](../voltage_sequence/README.md#75-matrix-constraints-and-rectangular-support) |
| End-to-end virtual gate example | [voltage_sequence §8](../voltage_sequence/README.md#8-full-end-to-end-example) |
| `resolve_voltages` round-trip test | [`virtual_gate_set_example.py`](../examples/virtual_gate_set_example.py) |
| External DC + virtual layers | [`virtual_dc_set_example.py`](../examples/virtual_dc_set_example.py) |

The [`virtual_gates/`](./) package re-exports `VirtualGateSet` from [`components/virtual_gate_set.py`](../components/virtual_gate_set.py) for backward-compatible imports.
