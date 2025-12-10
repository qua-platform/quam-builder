# QUAM Architecture: Superconducting Components (`quam_builder.architecture.superconducting`)

This directory defines the Python classes representing the components of a Quantum Abstract Machine (QUAM) architecture specifically designed for **superconducting qubit systems** (like transmons). These classes model the physical elements (qubits, resonators, drive lines, etc.) and serve as the building blocks assembled by the `quam_builder.builder` module to create a complete QUAM configuration object for controlling such systems.

The architecture is organized into the following categories:

## 1. QPU (`architecture/superconducting/qpu/`)

Defines the top-level structure of the Quantum Processing Unit (QPU).

- **`BaseQuam`**: An abstract base class defining the common structure for any QUAM representation, including dictionaries for qubits, qubit pairs, and wiring information.
- **`FixedFrequencyQPU`**: A concrete implementation inheriting from `BaseQuam`, specifically designed for QPUs composed primarily of fixed-frequency transmons. It holds collections of `FixedFrequencyTransmon` and `FixedFrequencyTransmonPair` objects.
- **`FluxTunableQPU`**: A concrete implementation inheriting from `BaseQuam`, designed for QPUs with flux-tunable transmons. It holds collections of `FluxTunableTransmon` and `FluxTunableTransmonPair` objects.

## 2. Qubit (`architecture/superconducting/qubit/`)

Defines the properties and operations associated with individual qubits.

- **`BaseTransmon`**: An abstract base class for transmon qubits. It includes common attributes like f_01, anharmonicity, T1, and associated components like readout resonators (`rr`) and XY drive lines (`xy`).
- **`FixedFrequencyTransmon`**: Inherits from `BaseTransmon`. Represents a transmon qubit with a fixed frequency. It typically includes attributes and methods specific to fixed frequency transmons.
- **`FluxTunableTransmon`**: Inherits from `BaseTransmon`. Represents a transmon qubit whose frequency can be tuned via a flux line. It includes a `FluxLine` component, as well as attributes and methods specific to flux tunable transmons.

## 3. Components (`architecture/superconducting/components/`)

Defines the auxiliary hardware components and control elements associated with qubits or their interactions.

- **`ReadoutResonator`**: Defines parameters for the readout resonator coupled to a qubit, including its frequency (`readout_frequency`), quality factor (`Q`), drive parameters (`readout_amplitude`, `readout_length`), time of flight (`time_of_flight`), and integration weights (`integration_weights`).
- **`XYDrive`**: Represents the microwave drive line for single-qubit gates (X, Y rotations). Includes parameters like the inferred intermediate frequency reference, and methods to related to the hardware (`get_output_power`).
- **`FluxLine`**: Defines the parameters for the flux bias line used to tune qubit frequency. Includes various attributes suc as the different flux bias offsets (`joint_offset`, `independent_offset`...), the corresponding flux points (`flux_point`), and the flux voltage settle time (`settle_time`) and methods to go to the specified bias points (`to_independent_idle`, `to_joint_idle`...) for instance.
- **`Mixer`**: Defines mixer calibration parameters, typically including the correction matrix (`correction_matrix`) to compensate for IQ imbalance and skewness.
- **`TunableCoupler`**: Models a tunable coupling element between qubits. Includes various attributes suc as the different flux bias offsets (`decouple_offset`, `interaction_offset`...), the corresponding flux points (`flux_point`), and the flux voltage settle time (`settle_time`) and methods to go to the specified bias points (`to_decouple_idle`, `to_interaction_idle`...) for instance.
- **`CrossResonance`**: Defines parameters specific to cross-resonance (CR) based two-qubit gates.
- **`ZZDrive`**: Represents drives used for dynamical decoupling or ZZ interaction cancellation.

## 4. Qubit Pair (`architecture/superconducting/qubit_pair/`)

Defines structures representing pairs of interacting qubits, holding parameters relevant to their joint operations (e.g., two-qubit gates).

- **`FixedFrequencyTransmonPair`**: Represents a pair of interacting fixed-frequency transmons. Contains the control and target qubit components, as well as parameters related to specific two-qubit gate implementations such as `ZZ_drive` or `cross_resonance`.
- **`FluxTunableTransmonPair`**: Represents a pair of interacting flux-tunable transmons. Contains the control and target qubit components, as well as parameters related to specific two-qubit gate implementations such as `coupler` or `mutual_flux_bias` for instance.

---

These architecture classes provide a structured way to represent the physical system and its control parameters within the QUAM framework.
