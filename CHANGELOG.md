# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [Unreleased]
### Changed
- Updated qualang-tools requirement `"qualang-tools>=0.22.0"`.
- **BREAKING:** `CZGate` renamed `flux_pulse_control` → `flux_pulse_qubit`, `flux_pulse_control_label` → `flux_pulse_qubit_label`, and the `apply()` parameters `amplitude_scale_control` → `amplitude_scale_qubit` and `duration_control` → `duration_qubit`. The moving qubit is now chosen via `qubit_pair.moving_qubit`.
- **BREAKING:** `BaseTransmon.readout_state_gef` default `pulse_name` changed from `"readout"` to `"readout_GEF"`. `add_default_transmon_pulses` now seeds a matching `readout_GEF` operation, so default-pulse users are unaffected; callers using custom resonator operations may need to either pass `pulse_name="readout"` explicitly or define a `readout_GEF` operation on their resonator.
### Added
- Updated the TWPA component with isolation pump and added corresponding builder functions.
- `FluxTunableTransmonPair.moving_qubit` (`Literal["control", "target"]`, default `"control"`) selects which qubit carries the flux pulse during two-qubit gates.
- `CZGate` now reads `qubit_pair.moving_qubit` to play the flux pulse on either the control or the target qubit.
- Default `readout_GEF` `SquareReadoutPulse` added to transmon resonators by `add_default_transmon_pulses` so `readout_state_gef` works out of the box.
Updated qualang-tools requirement `"qualang-tools>=0.22.0"`.
- Added `scipy>=1.10` as a runtime dependency (required by the gaussian-filtered pulses).
### Added
- Updated the TWPA component with isolation pump and added corresponding builder functions.
- Added `GaussianFilteredSquarePulse` to `quam_builder.common.pulses` (mirrors `quam.components.pulses`).
- Added `GaussianFilteredSymmetricBipolarPulse` and `SNZPulse` to `quam_builder.architecture.superconducting.components.pulses` (mirrors `quam.components.pulses`).
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

[Unreleased]: https://github.com/qua-platform/quam-builder/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/qua-platform/quam-builder/releases/tag/v0.3.0
[0.2.0]: https://github.com/qua-platform/quam-builder/releases/tag/v0.2.0
[0.1.2]: https://github.com/qua-platform/quam-builder/releases/tag/v0.1.2
[0.1.1]: https://github.com/qua-platform/quam-builder/releases/tag/v0.1.1
[0.1.0]: https://github.com/qua-platform/quam-builder/releases/tag/v0.1.0
