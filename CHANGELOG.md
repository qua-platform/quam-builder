# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [Unreleased]

### Added

- BSD-3-Clause `LICENSE` file, and the license in the package metadata.
- GitHub workflow `on-released.yml` that publishes the package to PyPI when a GitHub Release is published, using PyPI trusted publishing.
- Project URLs and classifiers in the package metadata.

### Fixed

- README links now point to GitHub, so they also work on PyPI. The broken link to a non-existent `nv_center` README is replaced by the `quantum_dots` README.

## [0.7.0] - 2026-11-09

### Added

- Macro class for the CR and CZ gate on fixed frequency transmons: `CRGate` and `StarkInducedCZGate` (#146).
- QPU class `FixedFrequencyZZDriveQuam` and associated `FixedFrequencyZZDriveTransmon`, `ZZDriveIQ`, and `ZZDriveMW` (#146).
- Architecture components for cross-resonance gates: `CrossResonanceDriveIQ`/`CrossResonanceDriveMW` channels, `XYDetunedDriveIQ`/`XYDetunedDriveMW`, CR gate macro parameters on `CRGate`, and builder wiring for default cross-resonance pulses on transmon pairs (#146).
- Pulse classes `SmoothFlatTopPulse`, `DragFlatTopPulse`, and `MultiderivativeCRPulse` (#146).
- `FlatTopGaussianPulse` and `FlatTopCosinePulse` accept either `flat_length` or `rise_fall_length`; the other is derived from `length` (#146).
- `DrachmaReadoutPulse.padding` as `(value, length_ns)` (default `(0, 0)`, which leaves the waveform unchanged): appends `length_ns` of constant `value` to the end of the pulse. `length` stays the total length, so the DRACHMA core spans `length - length_ns` samples (#162).

### Changed

- **BREAKING:** Dropped support for Python 3.9; the minimum is now 3.10. `requires-python` is now `>=3.10,<3.14`, which also allows 3.13 patch releases (previously excluded by `<=3.13`).
- **BREAKING:** `FixedFrequencyTransmonPair.zz_drive` is renamed to `zz`, and `FixedFrequencyTransmonPair.xy_detuned` is removed. Saved states that contain these keys must be updated before they load (#146).
- **BREAKING:** `CrossResonanceIQ`/`CrossResonanceMW` (module `components/cross_resonance.py`) are replaced by `CrossResonanceDriveIQ`/`CrossResonanceDriveMW` (module `components/cross_resonance_drive.py`); the unused `bell_state_fidelity` field is dropped. The `components/zz_drive.py` module is renamed to `components/zz.py` (#146).
- `set_output_power_mw_channel` now accepts full-scale powers in `[-11, 18]` dBm in 1 dB steps (previously 3 dB steps), and no longer needs the current value to compute the power (#146).
- `BaseTransmon.thermalization_time` now has a floor of 100 µs, which is also the default when `T1` is not set (previously 10 µs × `thermalization_time_factor`) (#146).
- **BREAKING:** `DrachmaReadoutPulse.amplitude` is now the peak of the no-Kerr waveform magnitude (previously the area divided by length). Existing saved states and calibration scripts still load but play a weaker waveform for the same stored value, so recalibrate the amplitude after upgrading. The amplitude is accepted in `[0, 0.99]` and validated at creation, so a stored value above 0.99 now fails at load time. The waveform raises if the I or Q peak goes above 1, which can happen with large self-Kerr, and the self-Kerr field estimate now uses the same scale as the played waveform (#162).

### Fixed

- `DrachmaReadoutPulse` self-Kerr correction now estimates the intracavity field with the complementary-state operator; the previous estimate was only correct for shared kappa and symmetric detunings (#162).
- `BaseTransmon.reset_qubit_active_gef` no longer crashes with `AttributeError`: the extra wait that read the non-existent `rr.res_deplete_time` is removed, because `readout_state_gef` already waits for `resonator.depletion_time` (#166).
- `BaseTransmon.reset_qubit_active_gef` now stops after `max_attempts` rounds (new argument, default 15) instead of looping forever, and its `readout_pulse_name` defaults to `"readout_GEF"` (#166).
- `ResetMacro` now forwards `max_attempts` for `reset_type="active_gef"`, as it already did for `"active"` (#166).

## [0.6.0] - 2026-09-28

### Added

- `DrachmaReadoutPulse` now supports per-state resonator linewidths (`kappa_ground_hz`, `kappa_excited_hz`). Equal values reproduce the previous shared-kappa waveform (#155).
- Optional self-Kerr correction on `DrachmaReadoutPulse` via `zeta_ground_hz` and `zeta_excited_hz` (default `0.0`, which leaves the waveform unchanged) (#155).
- `DrachmaReadoutPulse.depletion_time_ns` (default `16`): extra wait after the pulse for the resonator to decay before measurement (#155).

### Changed

- **BREAKING:** `DrachmaReadoutPulse.resonator_kappa_hz` is removed. Set `kappa_ground_hz` and `kappa_excited_hz` instead (use the old value for both to keep the previous waveform) (#155).

## [0.5.0] - 2026-08-19

### Added

- Added `BaseQuam.twpa_keepalive()` to keep sticky TWPA pumps on across a real-time loop (#123).
- Added default single-qubit gate macros for transmons (`MeasureMacro`, `ResetMacro`, `VirtualZMacro`, `DelayMacro`, `IdMacro`) (#101).
- Added `DrachmaReadoutPulse` readout scheme (#140).
- Added `custom_gates` section to `architecture/superconducting/README.md` documenting single-qubit macros and the `CZGate` two-qubit macro, including pulse-naming conventions and usage examples. Gate macros are currently specific to the superconducting architecture; `CZGate` requires `FluxTunableTransmonPair`.
- Added incremental add/remove helpers for qubits, channels, and ports, including typed port helpers ``add_mw_port`` (MW-FEM) and ``add_lf_port`` (LF-FEM / OPX+ baseband) with a required ``type="input"`` or ``type="output"`` argument (#121).

### Changed

- **BREAKING:** Active-reset `max_attempts` must be a strictly positive, non-boolean integer. `max_attempts=1` selects a single-shot measure-and-conditional-pi reset with no `while_` retry loop; values greater than one permit retries, and `max_attempts=0` is invalid (#138).

### Fixed

- Fixed TWPA pump initialization being skipped in subsequent QUA programs due to process-global deduplication state ([#122](https://github.com/qua-platform/quam-builder/issues/122)) (#137).
- Restored `AnyQuamQD` type alias (`Union[BaseQuamQD, LossDiVincenzoQuam]`) in `architecture.quantum_dots.qpu`. Required by `qualibration-libs` (`qualibration_libs/parameters/experiment.py`) (#142).
- `add_default_transmon_pair_macros` now passes `flux_pulse_qubit="const"` (was `flux_pulse_control="const"`) to `CZGate`, matching the field rename introduced in v0.4.0 and aligning with the `"const"` pulse added to every `FluxTunableTransmon` Z line by `add_default_transmon_pulses`.
- Applied black formatting across the entire repo (#128).

## [0.4.0] - 2026-05-26

### Added

- Updated the TWPA component with isolation pump and added corresponding builder functions.
- Added `quam_builder/common/pulses.py` with general-purpose pulse classes (`GaussianPulse`, `FlatTopGaussianPulse`, `FlatTopCosinePulse`, `GaussianFilteredSquarePulse`) shared across architectures.
- Added superconducting-specific pulse classes to `architecture/superconducting/components/pulses.py`: `FlatTopBlackmanPulse`, `BlackmanIntegralPulse`, `FlatTopTanhPulse`, `CosineBipolarPulse`, `GaussianFilteredSymmetricBipolarPulse`, and `SNZPulse`.
- Added `scipy>=1.10` as a runtime dependency (required by the gaussian-filtered pulses).
- Added `FluxTunableTransmonPair.moving_qubit` (`Literal["control", "target"]`, default `"control"`) to select which qubit carries the flux pulse during two-qubit gates.
- `CZGate` now reads `qubit_pair.moving_qubit` to play the flux pulse on either the control or the target qubit.
- Default `readout_GEF` `SquareReadoutPulse` added to transmon resonators by `add_default_transmon_pulses` so `readout_state_gef` works out of the box.

### Changed

- Updated qualang-tools requirement to `"qualang-tools>=0.22.0"`.
- **BREAKING:** `CZGate` renamed `flux_pulse_control` → `flux_pulse_qubit`, `flux_pulse_control_label` → `flux_pulse_qubit_label`, and the `apply()` parameters `amplitude_scale_control` → `amplitude_scale_qubit` and `duration_control` → `duration_qubit`. The moving qubit is now chosen via `qubit_pair.moving_qubit`.
- **BREAKING:** `BaseTransmon.readout_state_gef` default `pulse_name` changed from `"readout"` to `"readout_GEF"`. `add_default_transmon_pulses` now seeds a matching `readout_GEF` operation, so default-pulse users are unaffected; callers using custom resonator operations may need to either pass `pulse_name="readout"` explicitly or define a `readout_GEF` operation on their resonator.
- Renamed `builder/superconducting/pulses.py` → `add_default_pulses.py` to clarify its role as a builder helper and avoid naming clash with the architecture-level `pulses.py`.
- Renamed `builder/quantum_dots/pulses.py` → `add_default_pulses.py` and updated pulse imports to use explicit class imports; `GaussianPulse` now sourced from `quam_builder.common.pulses`.
- Renamed `builder/nv_center/pulses.py` → `add_default_pulses.py` and switched to explicit class imports from `quam.components.pulses`.
- Updated `architecture/quantum_dots/components/xy_drive.py` and `gate_set.py` to use explicit pulse class imports instead of the `pulses` module.

### Fixed

- Fix the default behavior of `def initialize_qpu(self, isolation: bool = False, **kwargs):` in the SC `BaseQuam`.
- `CZGate.apply()` now includes the tunable coupler channel in the initial and final `align()` calls, so coupler pulses no longer drift relative to the qubits.
- `BaseTransmon.reset_qubit_active_gef` now passes `keep_phase=True` to all `update_frequency` calls, preserving the qubit drive phase across the f12 detour during GEF active reset.

## [0.3.0] - 2026-03-31

### Added

- Added support for Python 3.13.
- Add support for cloud-based QMM instances in `machine.connect()`
- A custom QMM class can be specified in the network configuration, and enabled/disabled with the `use_custom_qmm` flag.
- TWPA: add `pumpline_attenuation` and `signalline_attenuation` (float, optional) attributes.
- BaseQuam , XYDriveBase and ReadoutResonatorBase: `extras` (dict) for additional QUAM-level attributes.

### Changed

- FluxTunableQuam.set_all_fluxes: `target` is now optional; when `target=None`, settle and align are applied to all qubits.

### Fixed

- NV center - fix invalid `SPCM` component.

## [0.2.0] - 2025-10-29

### Added

- Complete architecture for single NV centers.
- Macro class for the CZ gate on tunable transmons: `CZGate`
- Add the `CZGate` fidelity and extras as dictionaries.
- Architecture components for Quantum Dots: added support for `VoltageGate`, `GateSet`, `VoltageSequence`, `VirtualGateSet`, and `VirtualizationLayer`.

### Changed

- Fixed dev dependencies and added tool.uv.prerelease=allow to the pyproject.toml file.

## [0.1.2] - 2025-08-06

### Added

- tools - Added `power_tools.py` from qualibration-libs to remove the dependency.

### Fixed

- Remove qualibrate and xarray from the requirements.
- Fixed bug which created a self-reference when using external mixers.

## [0.1.1] - 2025-07-14

### Added

- Optional `num_IQ_pairs` argument to `declare_qua_variables`.

## [0.1.0] - 2025-05-07

### Added

- Architecture components for Flux Tunable Transmons.
- Architecture components for Fixed Frequency Transmons.
- Builder functions for the general QUAM wiring.
- Builder functions for Transmons.

[Unreleased]: https://github.com/qua-platform/quam-builder/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/qua-platform/quam-builder/releases/tag/v0.6.0
[0.5.0]: https://github.com/qua-platform/quam-builder/releases/tag/v0.5.0
[0.4.0]: https://github.com/qua-platform/quam-builder/releases/tag/v0.4.0
[0.3.0]: https://github.com/qua-platform/quam-builder/releases/tag/v0.3.0
[0.2.0]: https://github.com/qua-platform/quam-builder/releases/tag/v0.2.0
[0.1.2]: https://github.com/qua-platform/quam-builder/releases/tag/v0.1.2
[0.1.1]: https://github.com/qua-platform/quam-builder/releases/tag/v0.1.1
[0.1.0]: https://github.com/qua-platform/quam-builder/releases/tag/v0.1.0
