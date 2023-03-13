# Changelog
All notable changes to Q1Pulse will be documented in this file.

## \[0.8.5] - 2023-03-13

- Support qblox-instruments v0.9.0.

## \[0.8.4] - 2023-03-03

- Removed ADC calibration. It is not reliable.

## \[0.8.3] - 2023-02-08

- Do not start root-instrument if it has no active sequences.
- Disable continuous system error checking after initial configuration of all modules.
- Added short sleep before calibration to avoid calibration failures.

## \[0.8.2] - 2023-02-08

- Added QRM ADC calibration.
- Changed logging.info() to logger.info()
- Improved Exception and message on QRM input overload
- Allow suppression of input overload exception with set_exception_on_overload(False)

## \[0.8.1] - 2023-01-23

- Fixed compilation of ramps with (v_start-v_end) < 1 bit

## \[0.8.0] - 2022-12-22

- Update to qblox_instruments v0.8
- Added set_freq
- Changed arguments set_ph, set_ph_delta
- Added chirp to sequencer

## \[0.7.2] - 2022-12-20

- Added try/except around qcodes cache()

## \[0.7.1] - 2022-12-08

- Improved communication (configuration/upload) speed by postponing error checks.
- Use qcodes parameter cache to check whether setting has changed.

## \[0.7.0] - 2022-12-02

- Aligned version with qblox-instruments version
- Added `delete_acquisition_data` to QRM
- Improved performance with smarter calls to cluster/pulsar

## \[0.4.5] - 2022-11-16

### Fixed
- repeated_acquire with n=1
- Do not create empty directories if listing = False and json = False

### Changed
- Some minor performance improvements

## \[0.4.4] - 2022-08-19

### Fixed
- Phase reset for sequence repetition

## \[0.4.3] - 2022-08-16

### Added
- Added state flag "SEQUENCE PROCESSOR RT EXEC COMMAND UNDERFLOW"

### Fixed
- Slow ramps around 1 LSB per 100 ns.

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
