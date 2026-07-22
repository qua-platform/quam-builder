> This document covers hardware QuAM components: readout, transport, pulses, and sensor setup. For DC gates and virtual layers see [../voltage_sequence/README.md](../voltage_sequence/README.md). For spin qubits and XY drives see [../qpu/README.md](../qpu/README.md). For macros see [../operations/README.md](../operations/README.md).

# Quantum-dot hardware components

This folder holds the primary QuAM dataclasses used by quantum-dot and spin-qubit machines: voltage gates, dots, readout channels, XY drives, and custom pulse envelopes.

## Readout stack (RF)

Use **resonator readout** when the sensor dot is probed via an RF tone (SET-style or dispersive readout on an in/out line).

| Class | QuAM base | Typical hardware |
|-------|-----------|------------------|
| **`ReadoutResonatorSingle`** | `InOutSingleChannel` | LF-FEM baseband resonator (upsampling to MW mode) |
| **`ReadoutResonatorIQ`** | `InOutIQChannel` | LF-FEM + Octave / external mixer |
| **`ReadoutResonatorMW`** | `InOutMWChannel` | MW-FEM resonator |

All inherit **`ReadoutResonatorBase`** (`frequency_bare`) and support power helpers on IQ/MW variants via [`power_tools.py`](../../../tools/power_tools.py).

### Attaching readout to a sensor dot

A **`SensorDot`** extends **`QuantumDot`** with:

- **`readout_resonator`** — the RF channel used for PSB readout.
- **`readout_thresholds`** — per-`QuantumDotPair` discrimination threshold.
- **`readout_projectors`** — per-pair IQ projector weights (`Projector`: `wI`, `wQ`, `offset`).
- **`readout_reservoir`** — optional **`DrainSingle`** ohmic contact.

After wiring macros, each sensor resonator gets a default **`SquareReadoutPulse`** named `"readout"` (see [operations/README.md](../operations/README.md)). Pair-specific pulses can be named `"readout_{pair_id}"` when multiple pairs share one sensor.

### RF readout workflow

1. **Build** — register `SensorDot` with `readout_resonator` on the machine (builder or manual; see [`quam_qd_example.py`](../examples/quam_qd_example.py)).
2. **Calibrate** — set resonator frequency and power (`set_output_power` on IQ/MW); run `sensor_dot.calibrate_octave(QM)` when using Octave.
3. **Discrimination** — store threshold and projector per pair:

   ```python
   sensor._add_readout_params(
       quantum_dot_pair_id="dot1_dot2_pair",
       threshold=0.12,
       projector={"wI": 1.0, "wQ": 0.0, "offset": 0.0},
   )
   ```

4. **Measure in QUA** — `pair.measure()` (via **`MeasurePSBPairMacro`**) steps to the `"measure"` voltage point, aligns gates with the resonator, and calls **`SensorDotMeasureMacro`** for state assignment.

Example end-to-end: [`rabi_chevron.py`](../examples/rabi_chevron.py).

## Transport / DC readout

Use **transport readout** when the measurement is a DC current or conductance signal on an LF input (no resonator tone).

| Class | Role |
|-------|------|
| **`ReadoutTransportSingle`** | LF input-only transport measurement |
| **`ReadoutTransportSingleIO`** | In/out channel (pulse required for config even if amplitude is zero) |

Attach transport readout on a **`VoltageGate.readout`** field or directly on the sensor dot topology as in [`quam_qd_example.py`](../examples/quam_qd_example.py).

Example experiment: [`rabi_chevron_transport.py`](../examples/rabi_chevron_transport.py) (same Rabi–Chevron structure as the RF example, different readout path).

## Parallel readout and alignment

Voltage gates (sticky DC) and readout resonators run on **separate QUA elements** and execute in parallel unless synchronized.

**`MeasurePSBPairMacro`** (on `QuantumDotPair` / `LDQubitPair`) calls `qua.align(sensor_dot.readout_resonator.name, *gate_names)` before readout so the measure point and RF pulse are time-aligned. When integrated-voltage tracking is enabled, **`SensorDotMeasureMacro`** also reports readout duration so the voltage sequencer can call `track_sticky_duration`.

For multi-qubit programs, insert explicit `qua.align(...)` between XY pulses, voltage sequences, and readout blocks. See [`dcz_macro_example.py`](../examples/dcz_macro_example.py) and [`full_workflow_example.py`](../examples/full_workflow_example.py).

## Custom pulse shapes and windowing

Default XY pulses are **`Scalable*`** classes in [`pulses.py`](pulses.py), wired by [`pulse_catalog.py`](../operations/pulse_catalog.py):

| Family | Class | Notes |
|--------|-------|-------|
| Gaussian | `ScalableGaussianPulse` | `sigma_ratio` auto-scales with `length` |
| Square | `ScalableSquarePulse` | Flat-top envelope |
| Kaiser | `ScalableKaiserPulse` | Kaiser window (`beta=8`); strong spectral suppression |
| Hermite | `ScalableHermitePulse` | Gaussian × Hermite polynomial; tunable `hermite_coeff` |
| DRAG | `ScalableDragPulse` | Derivative pulse for leakage reduction |

**Windowing trade-offs:** Kaiser and Hermite reduce off-resonant spectral content compared to a bare Gaussian; DRAG adds a derivative term for IQ/MW drives. Switch the active family machine-wide with `machine.set_pulse_family("kaiser")` (propagates to all XY macros). See [`full_workflow_example.py`](../examples/full_workflow_example.py).

All default pulse **`length`** values must be **multiples of 4 ns** (OPX sample grid).

### Adding or overriding pulses

- **Override defaults at wiring time** — `wire_machine_macros(..., pulse_overrides=...)` or edit operations after wiring. Example: [`pulse_overrides_example.py`](../examples/pulse_overrides_example.py).
- **Add a pulse on one qubit** — `qubit.add_xy_pulse(name, pulse)` or `qubit.xy.add_pulse(name, pulse)`.
- **Custom macro** — point `XYDriveMacro.reference_pulse_name` at your operation; calibrate amplitude on the reference pulse (see [operations/README.md](../operations/README.md#single-qubit-gate-composition-model)).

**Baseband (`XYDriveSingle`):** pulses use real waveforms (`axis_angle=None`); rotation axis is selected by virtual-Z in the macro, not hardware IQ mixing.

**IQ / MW (`XYDriveIQ`, `XYDriveMW`):** default reference pulses use `axis_angle=0.0`; the macro applies virtual-Z for X/Y axis selection.

## DAC integration

**`DacSpec`** and **`QdacSpec`** on **`VoltageGate`** attach metadata for external DAC channels (e.g. QDAC-II trigger routing). The gate's **`offset_parameter`** can point at a QCoDeS driver for Python-side offsets while the OPX plays sticky pulses. See [`dac_spec.py`](dac_spec.py) and [`virtual_dc_set_example.py`](../examples/virtual_dc_set_example.py) for combined OPX + external-DC setups.

## Related components (brief)

| Component | Role | Doc |
|-----------|------|-----|
| **`QuantumDot`** / **`QuantumDotPair`** | Dot topology, detuning axis | [voltage_sequence/README.md](../voltage_sequence/README.md#9-exchange-only-qubits-detuning-axis) |
| **`BarrierGate`**, **`GlobalGate`** | Named gates on voltage channels | [../README.md](../README.md) |
| **`DrainSingle`**, **`SourceSingle`** | Reservoir contacts | Used with sensor readout reservoirs |
| **`XYDrive*`** | ESR/EDSR drive lines | [../qpu/README.md](../qpu/README.md) |

## Examples index

| Topic | Script |
|-------|--------|
| RF readout Rabi–Chevron | [`rabi_chevron.py`](../examples/rabi_chevron.py) |
| Transport readout | [`rabi_chevron_transport.py`](../examples/rabi_chevron_transport.py) |
| Pulse overrides | [`pulse_overrides_example.py`](../examples/pulse_overrides_example.py) |
| Kaiser family switch | [`full_workflow_example.py`](../examples/full_workflow_example.py) |
| Manual sensor + detuning setup | [`quam_qd_example.py`](../examples/quam_qd_example.py) |
