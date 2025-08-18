# QUAM Builder

This repository contains the `quam-builder`, a Python tool designed to programmatically construct QUAM (Quantum Abstract Machine) configurations for the Quantum Orchestration Platform (QOP).

The current version focuses primarily on superconducting qubits, though future versions will include other qubit types.

## Overview

The `quam-builder` simplifies the process of generating complex QUAM configurations by providing:

1.  **Modular Architecture Definitions:** Defines Python classes representing various components of a superconducting quantum processor (QPUs, qubits, readout resonators, drive lines, flux lines, couplers, etc.).

2.  **QOP Wiring Generation:** Functionality to automatically generate the `wiring` section of the QUAM configuration, mapping logical quantum elements to physical QOP controller ports (analog and digital).

3.  **Builder Functions:** Tools to assemble these components into a complete QUAM structure based on user-defined parameters and connectivity.

`quam-builder` is part of a larger ecosystem for quantum control:

* [**QUAM (Quantum Abstract Machine)**](https://qua-platform.github.io/quam/): The core specification and software for defining quantum machine components and states, which `quam-builder` helps generate.

* [**QUAlibrate**](https://qua-platform.github.io/qualibrate/): Qubit calibration software that utilizes the QUAM standard.

    * [**Qualibration-graph**](https://github.com/qua-platform/qua-libs): Calibration libraries that leverage `quam-builder` to create the necessary QUAM state representation.

## Core Functionality

### 1. Architecture Definition (`quam_builder.architecture`)

This module defines the hierarchical structure and data types for various QUAM components within a QUAM configuration tailored for specific qubit types:

* **QPU (`qpu`):** Base classes (`BaseQuam`) and specific implementations for different QPU types (`FixedFrequencyQPU`, `FluxTunableQPU`).

* **Qubits (`qubit`):** Defines transmon qubit types, including `BaseTransmon`, `FixedFrequencyTransmon`, and `FluxTunableTransmon`.

* **Components (`components`):** Represents the elements associated with qubits or qubit interactions, such as `ReadoutResonator`, `XYDrive`, or `TunableCoupler`for instance.

* **Qubit Pairs (`qubit_pair`):** Defines structures for pairs of interacting qubits, including parameters for two-qubit gates or couplings (`FixedFrequencyTransmonsPair`, `FluxTunableTransmonsPair`).

Note that several tools can be found in `quam_builder/tools`:
  - [power_tools](./quam_builder/tools/power_tools.py): Functions to precisely set and retrieve the output power (in dBm) for specific operations on `MWChannel` (`set_output_power_mw_channel`, `get_output_power_mw_channel`) and `IQChannel` (`set_output_power_iq_channel`, `get_output_power_iq_channel`) components defined in QUAM. Handles adjustments to full-scale power or gain/amplitude to achieve target power levels using helpers like `calculate_voltage_scaling_factor`.


Details on all the components can be found in [architecture/superconducting/README.md](./quam_builder/architecture/superconducting/README.md) and in the docstrings of the components.

### 2. QUAM Construction (`quam_builder.builder`)

This module provides functions to build the main QUAM structure:

* **`build_quam`:** The central function that takes QPU parameters, qubit details, and connectivity information to generate the complete QUAM Python object (excluding wiring).

* **Component Adders (`add_*_*_component`):** Helper functions (`add_transmon_drive_component`, or `add_transmon_pair_component` for instance) used by `build_quam` to populate the QUAM object with the appropriate components based on the specified architecture.

* **Pulse Definitions (`pulses`):** Contains functions to generate default pulse shapes and parameters (e.g., `drag_gauss_pulse`, `square_pulse`) commonly used in superconducting qubit experiments.

### 3. QOP Connectivity & Wiring (`quam_builder.builder.qop_connectivity`)

This module focuses on generating the `wiring` part of the QUAM configuration, connecting the logical elements defined in the architecture to the physical hardware ports of the QOP system:

* **`build_quam_wiring`:** The main function to create the `wiring` dictionary. It takes the QOP controllers, port assignments, and connectivity details.

* **Port Creation (`create_analog_ports`, `create_digital_ports`):** Functions to define the analog and digital ports on the specified QOP controllers (e.g., OPX+, Octave).

* **Wiring Creation (`create_wiring`):** Maps the logical elements (like qubit drive, readout, flux) to the defined controller ports based on the provided connectivity graph or list.

* **Helpers (`paths`, `channel_ports`, `get_digital_outputs`):** Utility functions for path finding in connectivity graphs and managing port information.

## Usage Examples

Examples for typical wiring configurations can be found in the [qua-platform/qua-libs](https://github.com/qua-platform/qua-libs) GitHub repository in the folder `qualibration_graphs/superconducting/quam_config/wiring_examples`.

The `wiring_examples` directory provides practical scripts demonstrating how to use `build_quam` and `build_quam_wiring` for different hardware configurations:

* **`wiring_opxp_octave.py`:** Example using OPX+ controllers and Octave modules.

* **`wiring_opxp_external_mixers.py`:** Example demonstrating configuration with external mixers instead of Octaves.

* **`wiring_lffem_mwfem.py`:** Example showcasing setup with LF-FEM and MW-FEM modules.

* **`wiring_lffem_octave.py`:** Example combining LF-FEM and Octave modules.

* **`wiring_mwfem_cross_resonance.py`:** Example specifically setting up wiring for cross-resonance drives using MW-FEMs.

These examples serve as templates for configuring various experimental setups.

## Extending QUAM Components

QUAM Builder provides a repository containing a standard set of components related to qubits, such as superconducting qubits (e.g., `FluxTunableTransmon`), resonators (e.g., `ReadoutResonatorIQ`), and associated pulses.
While this provides a solid foundation, it should not be viewed as a fixed set.
As you advance your calibration routines and develop custom calibration nodes and graphs, you may find it necessary to extend or modify these standard components.

There are several ways you might want to extend the QUAM components:

1.  **Adding Parameters:** You might need to add different parameters to the standard classes to accommodate specific characteristics of your hardware or calibration methods.
    For example, you may have a different coherence time metric you want to keep track of.

2.  **Adding Components:** You might want to introduce entirely new components.
    This could include custom pulse shapes tailored to your experiments or other quantum elements relevant to your setup.

### Method 1: Forking or Cloning QUAM Builder

One way to achieve these extensions is by creating a fork or a local clone of the main QUAM Builder repository.

1.  **Clone/Fork:** Obtain a local copy of the QUAM Builder source code.

2.  **Locate Components:** Navigate to the `architecture` folder within the repository.
    This folder contains the definitions for the different QUAM components.

3.  **Modify or Add:** You can now directly modify the existing Python classes for the components or add new Python files defining your custom components.

**Important Considerations:**

* **Compatibility:** When modifying existing components, be mindful of compatibility with existing calibration nodes.
    For example, if a calibration node expects a Transmon object to have a property named `T2echo`, renaming or removing this property in your modified class will break that node unless you also update the node's code to use the new property name.
    Try to maintain backward compatibility where possible or update your calibration nodes accordingly.

* **Synchronization:** If you intend to keep your local version synchronized with future updates from the main QUAM Builder repository, be aware that modifying the core component files can lead to merge conflicts when you try to pull the latest changes.
    This requires careful management of your version control.

### Method 2: Extension via QUAM Documentation

An alternative approach exists for extending QUAM components without directly cloning or forking the repository.
This method is detailed in the QUAM documentation on [Custom Components](https://qua-platform.github.io/quam/components/custom-components/).
Using this approach, you can subclass any existing classes in QUAM Builder, and add parameters and methods, as well as create new QUAM components.
However, note that this approach is generally more limited in scope, typically allowing only for the extension of existing components rather than fundamental modifications or additions of entirely new component types in the same manner as direct code modification.
