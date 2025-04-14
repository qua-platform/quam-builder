# QUAM Architecture: Superconducting Components (`quam_builder.architecture.superconducting`)

This directory defines the Python data structures (classes) representing the components of a Quantum Abstract Machine (QUAM) architecture specifically designed for **superconducting qubit systems** (like transmons). These classes model the physical elements (qubits, resonators, drive lines, etc.) and serve as the building blocks assembled by the `quam_builder.builder` module to create a complete QUAM configuration object for controlling such systems.

The architecture is organized into the following categories:

## 1. QPU (`architecture/superconducting/qpu/`)

Defines the top-level structure of the Quantum Processing Unit (QPU).

-   **`BaseQuam`**: An abstract base class inheriting from `QuamRoot`. Defines common structure including dictionaries for `octaves`, `mixers`, `qubits`, `qubit_pairs`, `wiring`, `network`, and lists for active elements. Manages connections (`connect`) and Octave configurations (`get_octave_config`).
-   **`FixedFrequencyQuam`**: Inherits from `BaseQuam`. Specifies `qubit_type` as `FixedFrequencyTransmon` and `qubit_pair_type` as `FixedFrequencyTransmonPair`. Holds collections of these specific types.
-   **`FluxTunableQuam`**: Inherits from `BaseQuam`. Specifies `qubit_type` as `FluxTunableTransmon` and `qubit_pair_type` as `FluxTunableTransmonPair`. Holds collections of these types and includes methods for managing flux states (`apply_all_flux_to_joint_idle`, `apply_all_flux_to_min`, etc.).

## 2. Qubit (`architecture/superconducting/qubit/`)

Defines the properties and operations associated with individual qubits.

-   **`BaseTransmon`**: An abstract base class inheriting from `Qubit`. Includes common attributes like `id`, `xy` drive, `resonator`, transition frequencies (`f_01`, `f_12`), `anharmonicity`, coherence times (`T1`, `T2ramsey`, `T2echo`), `thermalization_time_factor`, and methods for calibration (`calibrate_octave`), gate shape setting (`set_gate_shape`), readout (`readout_state`, `readout_state_gef`), and reset (`reset`, `reset_qubit_thermal`, `reset_qubit_active`, `reset_qubit_active_gef`).
-   **`FixedFrequencyTransmon`**: Inherits from `BaseTransmon`. Represents a transmon qubit with a fixed frequency. May include an optional `xy_detuned` channel. Defines `align` and `wait` methods for its channels (`xy`, `resonator`).
-   **`FluxTunableTransmon`**: Inherits from `FixedFrequencyTransmon`. Represents a transmon qubit whose frequency can be tuned via a flux line. Adds a `z` component (`FluxLine`) and flux-related parameters (`freq_vs_flux_01_quad_term`, `phi0_voltage`, etc.). Overrides `align` and `wait` to include the `z` channel.

## 3. Components (`architecture/superconducting/components/`)

Defines the auxiliary hardware components and control elements associated with qubits or their interactions. These often inherit from base `quam.components.channels` like `IQChannel`, `MWChannel`, `SingleChannel`, `InOutIQChannel`, `InOutMWChannel`, which provide core functionality for handling pulses, frequencies, and I/O.

-   **`ReadoutResonatorIQ` / `ReadoutResonatorMW`**: Inherit from `InOutIQChannel`/`InOutMWChannel` and `ReadoutResonatorBase`. Model the readout resonator. `ReadoutResonatorBase` includes attributes like `depletion_time`, `frequency_bare`, GEF parameters (`f_01`, `f_12`, `gef_centers`, `GEF_frequency_shift`), and methods for power calculation/setting. Pulses (like readout pulse) are defined within the `operations` dictionary inherited from channel classes.
-   **`XYDriveIQ` / `XYDriveMW`**: Inherit from `IQChannel`/`MWChannel` and `XYDriveBase`. Represent the microwave drive line for single-qubit gates. Handle intermediate/LO frequencies and operations (pulses like `x180`, `y90`, etc.) are defined in the inherited `operations` dictionary. Include methods for power calculation/setting.
-   **`FluxLine`**: Inherits from `SingleChannel`. Defines parameters for the flux bias line, including various offset points (`independent_offset`, `joint_offset`, `min_offset`, `arbitrary_offset`), the current `flux_point`, and `settle_time`. DC offset is set via `set_dc_offset`. Flux pulses are defined in the `operations` dictionary.
-   **`TunableCoupler`**: Inherits from `SingleChannel`. Models a tunable coupling element. Includes offset points (`decouple_offset`, `interaction_offset`, `arbitrary_offset`), `flux_point`, and `settle_time`. Control pulses are defined in the `operations` dictionary.
-   **`CrossResonanceIQ` / `CrossResonanceMW`**: Inherit from `IQChannel`/`MWChannel` and `CrossResonanceBase`. Define parameters for cross-resonance interactions. `CrossResonanceBase` includes `target_qubit_LO_frequency`, `target_qubit_IF_frequency`, and `bell_state_fidelity`. Drive pulses are defined in the `operations` dictionary.
-   **`ZZDriveIQ` / `ZZDriveMW`**: Inherit from `IQChannel`/`MWChannel` and `ZZDriveBase`. Represent drives for ZZ interactions. `ZZDriveBase` includes `target_qubit_LO_frequency`, `target_qubit_IF_frequency`, and `detuning`. Drive pulses are defined in the `operations` dictionary.
-   **`StandaloneMixer`**: Inherits from `quam.components.Mixer`. Represents an external mixer component, typically used within a `FrequencyConverter` which is stored in `BaseQuam.mixers`. Mixer calibration parameters are handled by the base `Mixer` class.

## 4. Qubit Pair (`architecture/superconducting/qubit_pair/`)

Defines structures representing pairs of interacting qubits.

-   **`FixedFrequencyTransmonPair`**: Inherits from `QuantumComponent`. Represents a pair of interacting `FixedFrequencyTransmon`s. Contains references to `qubit_control` and `qubit_target`, optional `cross_resonance` (`CrossResonanceIQ` or `MW`), optional `zz_drive` (`ZZDriveIQ` or `MW`), `confusion` matrix, and `extras`. Defines `align` and `wait` methods.
-   **`FluxTunableTransmonPair`**: Inherits from `QuantumComponent`. Represents a pair of interacting `FluxTunableTransmon`s. Contains references to `qubit_control` and `qubit_target`, an optional `coupler` (`TunableCoupler`), `mutual_flux_bias`, and `extras`. Defines `align`, `wait`, and `to_mutual_idle` methods.

---

These architecture classes provide a structured way to represent the physical system and its control parameters within the QUAM framework, reflecting the actual implementation in the Python code.