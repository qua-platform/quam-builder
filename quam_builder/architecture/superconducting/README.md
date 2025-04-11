# QUAM Architecture: Superconducting Components (`quam_builder.architecture.superconducting`)

This directory defines the Python data structures (classes) representing the components of a Quantum Abstract Machine (QUAM) architecture specifically designed for **superconducting qubit systems** (like transmons). These classes model the physical elements (qubits, resonators, drive lines, etc.) and serve as the building blocks assembled by the `quam_builder.builder` module to create a complete QUAM configuration object for controlling such systems.

The architecture is organized into the following categories:

## 1. QPU (`architecture/superconducting/qpu/`)

Defines the top-level structure of the Quantum Processing Unit (QPU).

- **`BaseQuam`**: An abstract base class defining the common structure for any QUAM representation, including dictionaries for qubits, qubit pairs, and wiring information.
- **`FixedFrequencyQPU`**: A concrete implementation inheriting from `BaseQuam`, specifically designed for QPUs composed primarily of fixed-frequency transmons. It holds collections of `FixedFrequencyTransmon` and `FixedFrequencyTransmonsPair` objects.
- **`FluxTunableQPU`**: A concrete implementation inheriting from `BaseQuam`, designed for QPUs with flux-tunable transmons. It holds collections of `FluxTunableTransmon` and `FluxTunableTransmonsPair` objects.

## 2. Qubit (`architecture/superconducting/qubit/`)

Defines the properties and operations associated with individual qubits.

- **`BaseTransmon`**: An abstract base class for transmon qubits. It includes common attributes like EC, EJ, g, levels, and associated components like readout resonators (`rr`) and XY drive lines (`xy`).
- **`FixedFrequencyTransmon`**: Inherits from `BaseTransmon`. Represents a transmon qubit with a fixed frequency. It typically includes `ReadoutResonator` and `XYDrive` components.
- **`FluxTunableTransmon`**: Inherits from `BaseTransmon`. Represents a transmon qubit whose frequency can be tuned via a flux line. In addition to readout and XY drive, it includes a `FluxLine` component and potentially parameters for ZZ interactions (`zz`).

## 3. Components (`architecture/superconducting/components/`)

Defines the auxiliary hardware components and control elements associated with qubits or their interactions.

- **`ReadoutResonator`**: Defines parameters for the readout resonator coupled to a qubit, including its frequency (`readout_frequency`), quality factor (`Q`), drive parameters (`readout_amplitude`, `readout_length`), time of flight (`time_of_flight`), and integration weights (`integration_weights`).
- **`XYDrive`**: Represents the microwave drive line for single-qubit gates (X, Y rotations). Includes parameters like intermediate frequency (`f01_if`), maximum amplitude (`pi_amp`), pulse shapes (`pi_pulse`, `ramsey_pulse`), and mixer calibration (`mixer`).
- **`FluxLine`**: Defines the parameters for the flux bias line used to tune qubit frequency. Includes maximum voltage (`max_voltage`), voltage points for specific frequencies (`voltage_points`), pulse shapes (`flux_pulse`), and distortion corrections (`distortions`).
- **`TunableCoupler`**: Models a tunable coupling element between qubits. Includes parameters like coupling strength (`coupling`), operating frequency (`frequency`), and control pulse parameters (`turn_on_pulse`, `turn_off_pulse`).
- **`CrossResonance`**: Defines parameters specific to cross-resonance (CR) based two-qubit gates. Includes attributes like drive frequency (`cr_if`), pulse shapes (`cr_pulse`), and amplitudes (`cr_amp`). Often associated with a specific `XYDrive` line acting on a target qubit.
- **`ZZDrive`**: Represents drives used for dynamical decoupling or ZZ interaction cancellation. Includes parameters like frequency (`zz_if`), amplitude (`zz_amp`), and pulse shape (`zz_pulse`).
- **`Mixer`**: Defines mixer calibration parameters, typically including the correction matrix (`correction_matrix`) to compensate for IQ imbalance and skewness.

## 4. Qubit Pair (`architecture/superconducting/qubit_pair/`)

Defines structures representing pairs of interacting qubits, holding parameters relevant to their joint operations (e.g., two-qubit gates).

- **`FixedFrequencyTransmonsPair`**: Represents a pair of interacting fixed-frequency transmons. May contain parameters related to static ZZ coupling or specific two-qubit gate implementations suitable for fixed-frequency systems. Often includes components like `CrossResonance` or `ZZDrive`.
- **`FluxTunableTransmonsPair`**: Represents a pair of interacting flux-tunable transmons. Includes parameters for two-qubit gates that often involve flux pulsing, such as iSWAP or CZ gates. May contain components like `FluxLine` (for the interaction pulse), `TunableCoupler`, or specific gate pulse definitions.

---

These architecture classes provide a structured way to represent the physical system and its control parameters within the QUAM framework.
