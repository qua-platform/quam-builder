# Architecture

The `quam_builder.architecture` package defines Python classes that represent the components of a QUAM configuration. The classes are grouped by qubit family.

## Superconducting

### QPU

::: quam_builder.architecture.superconducting.qpu.base_quam
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.qpu.fixed_frequency_quam
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.qpu.flux_tunable_quam
    options:
      heading_level: 4

### Qubit

::: quam_builder.architecture.superconducting.qubit.base_transmon
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.qubit.flux_tunable_transmon
    options:
      heading_level: 4

### Components

::: quam_builder.architecture.superconducting.components.readout_resonator
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.components.xy_drive
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.components.flux_line
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.components.tunable_coupler
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.components.cross_resonance
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.components.zz_drive
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.components.mixer
    options:
      heading_level: 4

::: quam_builder.architecture.superconducting.components.twpa
    options:
      heading_level: 4

---

## NV Center

### QPU

::: quam_builder.architecture.nv_center.qpu.nv_center_quam
    options:
      heading_level: 4

### Qubit

::: quam_builder.architecture.nv_center.qubit.nv_center_spin
    options:
      heading_level: 4

### Components

::: quam_builder.architecture.nv_center.components.laser
    options:
      heading_level: 4

::: quam_builder.architecture.nv_center.components.spcm
    options:
      heading_level: 4

::: quam_builder.architecture.nv_center.components.xy_drive
    options:
      heading_level: 4

---

## Quantum Dots

### QPU

::: quam_builder.architecture.quantum_dots.qpu.base_quam_qd
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.qpu.loss_divincenzo_quam
    options:
      heading_level: 4

### Qubit

::: quam_builder.architecture.quantum_dots.qubit.ld_qubit
    options:
      heading_level: 4

### Components

::: quam_builder.architecture.quantum_dots.components.voltage_gate
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.gate_set
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.virtual_gate_set
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.virtual_dc_set
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.quantum_dot
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.quantum_dot_pair
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.sensor_dot
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.barrier_gate
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.global_gate
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.reservoir
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.readout_resonator
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.readout_transport
    options:
      heading_level: 4

::: quam_builder.architecture.quantum_dots.components.xy_drive
    options:
      heading_level: 4
