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

- **`readout_resonator`** — the channel used for RF readout.
- **`readout_thresholds`** — per-`QuantumDotPair` discrimination threshold.
- **`readout_reservoir`** — optional **`DrainSingle`** ohmic contact.

After wiring macros, each sensor resonator gets a default **`SquareReadoutPulse`** named `"readout"` (see [operations/README.md](../operations/README.md)). Pair-specific pulses can be named `"readout_{pair_id}"` when multiple pairs share one sensor.

### RF readout workflow

1. **Build** — register `SensorDot` with `readout_resonator` on the machine (builder, or by hand in [`manual_dots_example.py`](../examples/connectivity/manual_dots_example.py)).
2. **Calibrate** — set resonator frequency and power (`set_output_power` on IQ/MW); run `sensor_dot.calibrate_octave(QM)` when using Octave.
3. **Discrimination** — rotate the IQ plane with readout-pulse **integration weights**, then store a per-pair threshold on I:

   ```python
   pulse = sensor.readout_resonator.operations["readout"]
   pulse.integration_weights_angle = 0.0  # 0 → discriminate on I
   sensor.readout_thresholds["dot1_dot2_pair"] = 0.12
   ```

4. **Measure in QUA** — `pair.measure()` (via **`MeasurePSBPairMacro`** see [operations/default_macros/state_macros.py](../operations/default_macros/state_macros.py)) steps to the `"measure"` voltage point, aligns gates with the resonator, and calls **`SensorDotMeasureMacro`** for state assignment.

Example end-to-end: [`rabi_chevron.py`](../examples/experiments/rabi_chevron.py).

## Transport / DC readout

Use **transport readout** when the measurement is a DC current or conductance signal on an LF input (no resonator tone).

| Class | Role |
|-------|------|
| **`ReadoutTransportSingle`** | LF input-only transport measurement |
| **`ReadoutTransportSingleIO`** | In/out channel (pulse required for config even if amplitude is zero) |

Attach transport readout on a **`VoltageGate.readout`** field or on the sensor dot's `readout_reservoir`.

## Parallel readout and alignment

Voltage gates (sticky DC) and readout resonators run on **separate QUA elements** and execute in parallel unless synchronized.

**`MeasurePSBPairMacro`** (on `QuantumDotPair` / `LDQubitPair`) calls `qua.align(sensor_dot.readout_resonator.name, *gate_names)` before readout so the measure point and RF pulse are time-aligned. When integrated-voltage tracking is enabled, **`SensorDotMeasureMacro`** also reports readout duration so the voltage sequencer can call `track_sticky_duration`.

For multi-qubit programs, insert explicit `qua.align(...)` between XY pulses, voltage sequences, and readout blocks. [`macro_overrides_example.py`](../examples/macros/macro_overrides_example.py) aligns the two qubit XY channels inside its CZ macro.

## Custom pulse shapes and windowing

Default XY pulses are **`Scalable*`** classes in [`pulses.py`](pulses.py), wired by [`pulse_catalog.py`](../operations/pulse_catalog.py):

| Family | Class | Notes |
|--------|-------|-------|
| Gaussian | `ScalableGaussianPulse` | `sigma_ratio` auto-scales with `length` |
| Square | `ScalableSquarePulse` | Flat-top envelope |
| Kaiser | `ScalableKaiserPulse` | Kaiser window (`beta=8`); strong spectral suppression |
| Hermite | `ScalableHermitePulse` | Gaussian × Hermite polynomial; tunable `hermite_coeff` |
| DRAG | `ScalableDragPulse` | Derivative pulse for leakage reduction |

**Windowing trade-offs:** Kaiser and Hermite reduce off-resonant spectral content compared to a bare Gaussian; DRAG adds a derivative term for IQ/MW drives. Switch the active family machine-wide with `machine.set_pulse_family("kaiser")` (propagates to all XY macros). See [`pulse_overrides_example.py`](../examples/macros/pulse_overrides_example.py).

All default pulse **`length`** values must be **multiples of 4 ns** (OPX sample grid).

### Adding or overriding pulses

- **Override defaults at wiring time** — `wire_machine_macros(..., pulse_overrides=...)` or edit operations after wiring. Example: [`pulse_overrides_example.py`](../examples/macros/pulse_overrides_example.py).
- **Add a pulse on one qubit** — `qubit.add_xy_pulse(name, pulse)` or `qubit.xy.add_pulse(name, pulse)`.
- **Custom macro** — point `XYDriveMacro.reference_pulse_name` at your operation; calibrate amplitude on the reference pulse (see [operations/README.md](../operations/README.md#single-qubit-gate-composition-model)).

**Baseband (`XYDriveSingle`):** pulses use real waveforms (`axis_angle=None`); rotation axis is selected by virtual-Z in the macro, not hardware IQ mixing.

**IQ / MW (`XYDriveIQ`, `XYDriveMW`):** default reference pulses use `axis_angle=0.0`; the macro applies virtual-Z for X/Y axis selection.

## DAC integration

A **`VoltageGate`** can carry both an OPX output and an external DC source, so a QDAC and the OPX can take part in the same experiment. **`DacSpec`** and **`QdacSpec`** attach metadata for that DC channel (for example QDAC-II trigger routing). **`offset_parameter`** points at the instrument driver, and **`VirtualDCSet`** writes the slow bias through it while the OPX plays sticky pulses on the same gate.

[`virtual_dc_set_example.py`](../examples/voltages/virtual_dc_set_example.py) is the DC half: it builds a **`VirtualDCSet`**, resolves virtual voltages onto DAC offsets, and checks the per-channel limit. It does not play an OPX pulse. The OPX virtual-layer path is [`virtual_gate_set_example.py`](../examples/voltages/virtual_gate_set_example.py). Channel metadata lives in [`dac_spec.py`](dac_spec.py).

**`QdacSpec`** exposes more of the Qdac-II specific functionality but is subclassing **`DacSpec`**

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
| RF readout Rabi–Chevron | [`rabi_chevron.py`](../examples/experiments/rabi_chevron.py) |
| Pulse overrides | [`pulse_overrides_example.py`](../examples/macros/pulse_overrides_example.py) |
| Kaiser family switch | [`pulse_overrides_example.py`](../examples/macros/pulse_overrides_example.py) |
| Manual dots, sensors, and QDAC ports | [`manual_dots_example.py`](../examples/connectivity/manual_dots_example.py) |
