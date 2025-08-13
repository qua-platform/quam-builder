# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [Unreleased]

## [0.1.2] - 2025-08-06
### Added
- tools - Added `power_tools.py` from qualibration-libs to remove the dependency. 
### Fixed
- Remove qualibrate and xarray from the requirements.
- Fixed bug which created a self-reference when using external mixers.

## [0.1.2] - 2025-07-25
### Added
- QuamMacros for Cross Resonance and CZ.
- Architecture components for Flux Tunable Cross Drive TransmonPair.
- Fix for `upconverter_frequency` property under `XYDriveMW`.  

## [0.1.1] - 2025-07-14
### Added
- Optional `num_IQ_pairs` argument to `declare_qua_variables`.  

## [0.1.0] - 2025-05-07
### Added
- Architecture components for Flux Tunable Transmons.
- Architecture components for Fixed Frequency Transmons.
- Builder functions for the general QUAM wiring.
- Builder functions for Transmons.

[Unreleased]: https://github.com/qua-platform/quam-builder/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/qua-platform/quam-builder/releases/tag/v0.1.2
[0.1.1]: https://github.com/qua-platform/quam-builder/releases/tag/v0.1.1
[0.1.0]: https://github.com/qua-platform/quam-builder/releases/tag/v0.1.0
