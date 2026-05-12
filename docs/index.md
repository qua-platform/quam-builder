# QUAM Builder

`quam-builder` is a Python tool designed to programmatically construct **QUAM (Quantum Abstract Machine)** configurations for the **Quantum Orchestration Platform (QOP)**.

The current version implements superconducting qubits, single NV centers, and quantum dot / spin qubit systems. Future versions will include other qubit types.

---

## What's Inside

<div class="grid cards" markdown>

- :material-book-open-variant: **[Guides](guides/index.md)**

    ---

    Architecture-specific narrative documentation: superconducting transmons, quantum dot / spin qubit voltage control, and the pylint QUA plugin.

- :material-api: **[API Reference](api/index.md)**

    ---

    Auto-generated reference for `quam_builder.architecture`, `quam_builder.builder`, and `quam_builder.tools` derived from source docstrings.

- :material-github: **[Source on GitHub](https://github.com/qua-platform/quam-builder)**

    ---

    Browse the code, file issues, and contribute on GitHub.

- :material-school: **[QOP Documentation](https://docs.quantum-machines.co/latest/)**

    ---

    The main Quantum Orchestration Platform documentation hub.

</div>

---

## Overview

The `quam-builder` simplifies the process of generating complex QUAM configurations by providing:

1. **Modular Architecture Definitions** — Python classes representing components of superconducting, NV center, and quantum dot quantum processors (QPUs, qubits, readout resonators, drive lines, flux lines, couplers, lasers, SPCMs, voltage gates, etc.).
2. **QOP Wiring Generation** — Functionality to automatically generate the `wiring` section of the QUAM configuration, mapping logical quantum elements to physical QOP controller ports (analog and digital).
3. **Builder Functions** — Tools to assemble these components into a complete QUAM structure based on user-defined parameters and connectivity.

`quam-builder` is part of a larger ecosystem for quantum control:

- **[QUAM (Quantum Abstract Machine)](https://qua-platform.github.io/quam/)** — The core specification and software for defining quantum machine components and states, which `quam-builder` helps generate.
- **[QUAlibrate](https://qua-platform.github.io/qualibrate/)** — Qubit calibration software that uses the QUAM standard.
    - **[Qualibration-graph](https://github.com/qua-platform/qua-libs)** — Calibration libraries that leverage `quam-builder` to create the necessary QUAM state representation.

## Core Functionality

### 1. Architecture Definition (`quam_builder.architecture`)

Defines the hierarchical structure and data types for QUAM components, organized by qubit type:

- **QPU** — Base classes (`BaseQuam`) and concrete implementations (`FixedFrequencyQPU`, `FluxTunableQPU`, `NVCenterQPU`, quantum dot QPUs).
- **Qubits** — Transmon types (`BaseTransmon`, `FixedFrequencyTransmon`, `FluxTunableTransmon`), `NVCenter`, and quantum dot qubits.
- **Components** — Auxiliary control hardware (`ReadoutResonator`, `XYDrive`, `FluxLine`, `TunableCoupler`, `VoltageGate`, etc.).
- **Qubit Pairs** — Structures for interacting qubit pairs and two-qubit gate parameters.

See the [Superconducting Guide](guides/superconducting.md) and [Quantum Dots Guide](guides/quantum_dots.md) for details.

### 2. QUAM Construction (`quam_builder.builder`)

- **`build_quam`** — Central function to assemble QPU parameters, qubit details, and connectivity into a complete QUAM Python object.
- **Component Adders** — Helper functions like `add_transmon_drive_component` and `add_transmon_pair_component` used by `build_quam`.
- **Pulse Definitions** — Default pulse shapes (e.g., `drag_gauss_pulse`, `square_pulse`) for superconducting qubit and NV center experiments.

### 3. QOP Connectivity & Wiring (`quam_builder.builder.qop_connectivity`)

- **`build_quam_wiring`** — Creates the `wiring` dictionary connecting logical elements to physical QOP controller ports.
- **Port Creation** — `create_analog_ports`, `create_digital_ports` for OPX+, Octave, and FEM modules.
- **Wiring Creation** — Maps logical elements (qubit drive, readout, flux) to controller ports based on connectivity.

## Usage Examples

Typical wiring configurations are available in the [qua-platform/qua-libs](https://github.com/qua-platform/qua-libs) repository under `qualibration_graphs/superconducting/quam_config/wiring_examples` and `qualibration_graphs/nv_center/quam_config/wiring_examples`. Examples include:

- `wiring_opxp_octave.py` — OPX+ controllers with Octave modules.
- `wiring_opxp_external_mixers.py` — OPX+ with external mixers instead of Octaves.
- `wiring_lffem_mwfem.py` — LF-FEM and MW-FEM modules.
- `wiring_lffem_octave.py` — LF-FEM combined with Octave modules.
- `wiring_mwfem_cross_resonance.py` — MW-FEM wiring for cross-resonance drives.

In-repo quantum dot examples are available under `quam_builder/architecture/quantum_dots/examples/`.

## Extending QUAM Components

You can extend QUAM components in two ways:

1. **Forking or Cloning** — Modify existing classes directly under `quam_builder/architecture/`. Be mindful of compatibility with calibration nodes and merge conflicts on upstream sync.
2. **Subclassing via QUAM** — Subclass existing classes following the [Custom Components guide](https://qua-platform.github.io/quam/components/custom-components/). More limited but does not require modifying the upstream code.

## Installation

```bash
pip install quam-builder
```

For development setup, see the [contributing guide](https://github.com/qua-platform/quam-builder/blob/main/CONTRIBUTING.md).
