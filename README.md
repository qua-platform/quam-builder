# QUAM Builder

This repository contains the `quam-builder`, a Python tool designed to programmatically construct QUAM (Quantum Abstract Machine) configurations for the Quantum Orchestration Platform (QOP).

The current version focuses primarily on superconducting qubits, though future versions will include other qubit types.

## Overview

The `quam-builder` simplifies the process of generating complex QUAM configurations by providing:

1.  **Modular Architecture Definitions:** Defines Python classes representing various components of a superconducting quantum processor (QPUs, qubits, readout resonators, drive lines, flux lines, couplers, etc.).
2.  **Builder Functions:** Tools to assemble these components into a complete QUAM structure based on user-defined parameters and connectivity.
3.  **QOP Wiring Generation:** Functionality to automatically generate the `wiring` section of the QUAM configuration, mapping logical quantum elements to physical QOP controller ports (analog and digital).

`quam-builder` is part of a larger ecosystem for quantum control:

- **[QUAM (Quantum Abstract Machine)](https://qua-platform.github.io/quam/)**: The core specification and software for defining quantum machine components and states, which `quam-builder` helps generate.
- **[QUAlibrate](https://qua-platform.github.io/qualibrate/)**: Qubit calibration software that utilizes the QUAM standard.
- **[qua-libs](https://github.com/qua-platform/qua-libs)**: Calibration libraries that leverage `quam-builder` to create the necessary QUAM state representation.

## Core Functionality

### 1. Architecture Definition (`quam_builder.architecture`)

This module defines the hierarchical structure and data types for various QUAM components within a QUAM configuration tailored for superconducting qubits:

- **QPU (`qpu`):** Base classes (`BaseQuam`) and specific implementations for different QPU types (`FixedFrequencyQPU`, `FluxTunableQPU`).
- **Qubits (`qubit`):** Defines transmon qubit types, including `BaseTransmon`, `FixedFrequencyTransmon`, and `FluxTunableTransmon`.
- **Components (`components`):** Represents the elements associated with qubits or qubit interactions:
  - `ReadoutResonator`: Defines readout resonator properties and operations.
  - `XYDrive`: Represents the microwave drive line for qubit control.
  - `FluxLine`: Defines the flux bias line for frequency tuning.
  - `TunableCoupler`: Models tunable coupling elements between qubits.
  - `CrossResonance`: Defines parameters for cross-resonance gates.
  - `ZZDrive`: Represents drives for ZZ interactions/cancellation.
  - `Mixer`: Defines mixer calibration parameters (correction matrix).
- **Qubit Pairs (`qubit_pair`):** Defines structures for pairs of interacting qubits, including parameters for two-qubit gates or couplings (`FixedFrequencyTransmonsPair`, `FluxTunableTransmonsPair`).

Details on all the components can be found in [architecture/superconducting/README.md](./quam_builder/architecture/superconducting/README.md) and in the docstrings of the components.

### 2. QUAM Construction (`quam_builder.builder.superconducting`)

This module provides functions to build the main QUAM structure:

- **`build_quam`:** The central function that takes QPU parameters, qubit details, and connectivity information to generate the complete QUAM Python object (excluding wiring).
- **Component Adders (`add_transmon_*_component`):** Helper functions (`add_transmon_drive_component`, `add_transmon_resonator_component`, `add_transmon_flux_component`, `add_transmon_pair_component`) used by `build_quam` to populate the QUAM object with the appropriate components based on the specified architecture.
- **Pulse Definitions (`pulses`):** Contains functions to generate default pulse shapes and parameters (e.g., `drag_gauss_pulse`, `square_pulse`) commonly used in superconducting qubit experiments.

### 3. QOP Connectivity & Wiring (`quam_builder.builder.qop_connectivity`)

This module focuses on generating the `wiring` part of the QUAM configuration, connecting the logical elements defined in the architecture to the physical hardware ports of the QOP system:

- **`build_quam_wiring`:** The main function to create the `wiring` dictionary. It takes the QOP controllers, port assignments, and connectivity details.
- **Port Creation (`create_analog_ports`, `create_digital_ports`):** Functions to define the analog and digital ports on the specified QOP controllers (e.g., OPX+, Octave).
- **Wiring Creation (`create_wiring`):** Maps the logical elements (like qubit drive, readout, flux) to the defined controller ports based on the provided connectivity graph or list.
- **Helpers (`paths`, `channel_ports`, `get_digital_outputs`):** Utility functions for path finding in connectivity graphs and managing port information.

## Usage Examples

Examples for typical wiring configurations can be found in the [qua-platform/qua-libs](https://github.com/qua-platform/qua-libs) GitHub repository in the folder `Quantum-Control-Applications-QUAM/Superconducting/quam_config/wiring_examples`.

The `wiring_examples` directory provides practical scripts demonstrating how to use `build_quam` and `build_quam_wiring` for different hardware configurations:

- **`wiring_opxp_octave.py`:** Example using OPX+ controllers and Octave modules.
- **`wiring_opxp_external_mixers.py`:** Example demonstrating configuration with external mixers instead of Octaves.
- **`wiring_lffem_mwfem.py`:** Example showcasing setup with LF-FEM and MW-FEM modules.
- **`wiring_lffem_octave.py`:** Example combining LF-FEM and Octave modules.
- **`wiring_mwfem_cross_resonance.py`:** Example specifically setting up wiring for cross-resonance drives using MW-FEMs.

These examples serve as templates for configuring various experimental setups.
