# Changelog
All notable changes to Q1Pulse will be documented in this file.

## \[0.4.2] - 2022-07-21

### Changed
- Improved performance: use dict argument to set sequence.
- Improved performance: disable sequencers without meaningful sequence.

## \[0.4.1] - 2022-07-19

### Added
- Added mixer_gain_ratio and mixer_phase_offset_degree properties to sequencer.

## \[0.4.0] - 2022-07-08

### Added
- Support Qblox Cluster
- Support RF modules
- Added set_out_offset with mV value for RF and non-RF modules.

### Fixed
- Always write QRM sequences before running. Otherwise the acquisition data is not cleared.

### Changed
- More compact sequence/json output to avoid buffer overrun of qblox compiler.

### Deleted
- Removed support for qblox_instruments < v0.6.0

## \[0.3.0] - 2022-04-13
### Changed
- Update for API changes of qblox_instruments v0.6
  - Note: Still backwards compatible with qblox_instruments v0.5

## \[0.2.0] - 2022-03-07
### Added
- check system state upon initialization and before every program run.
- made traceback of q1pulse instructions configurable
- set nco frequency on sequencer in program

### Fixed
- Proper handling of all QCM/QRM state flags

## \[0.1.0] - 2022-01-29
First labeled release. Start of dev branch and change logging.
