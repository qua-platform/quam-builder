# VoltageSequence implementation

`GateSet` and `VoltageSequence` are implemented in this package. Architecture code re-exports them for backward-compatible imports (e.g. `from quam_builder.architecture.quantum_dots.voltage_sequence import VoltageSequence`).

**Canonical documentation:** [quantum-dot voltage sequence README](../../architecture/quantum_dots/voltage_sequence/README.md).

Current defaults (do not copy older zeroing or compensation numbers from elsewhere):

- **`keep_levels=True`** — omitted physical and virtual gate names keep their last value. Pass `keep_levels=False` (or an explicit `0.0`) to treat omitted gates as 0 V.
- **`apply_compensation_pulse(max_voltage=0.05)`** — compensation amplitude limit is 0.05 V.
- **`ramp_to_zero(..., reset_tracker=False)`** — ramping to zero does **not** reset integrated-voltage trackers unless `reset_tracker=True`.
