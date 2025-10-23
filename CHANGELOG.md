# Changelog
All notable changes to Q1Pulse will be documented in this file.

## \[0.18.1] - 2925-10-23

- Added `acquire_ttl` and associated QCoDeS parameters.
- Use `update_sequence`.
- Check waveform memory and weights memory allocation before uploading.
- Added `get_scope_data`.
- Removed sleeps when polling for status.

## \[0.18.0] - 2025-10-08

- Updates for qblox-instruments v0.18.0
- Use `as_numpy=True` in `get_acquisitions`.
- Use SCPI transaction in TurboCluser for `get_acquisitions`.

## \[0.17.5] - 2025-08-05

- Fix illegal wait 1 ns.

## \[0.17.4] - 2025-07-16

- Improved KeyboardInterrupt handling.

## \[0.17.3] - 2025-07-08

- Implemented scheduling on 1 ns resolution.
- Optimized code for ramps to generate less Q1ASM instructions (10 to 20% less code).
- Dropped support for qblox-instruments < v0.12.0
- Internal change: always path 0 also for odd output channels.

## \[0.17.2] - 2025-06-19

- Improved performance of TurboCluster with another 10%.

## \[0.17.1] - 2025-06-13

- Sort sequencers for faster upload.
- Fixed TurboCluster for qblox-instruments v0.11

## \[0.17.0] - 2025-06-04

- Update to qblox-instruments v0.17

## \[0.16.4] - 2025-06-02

- Fixed TurboCluster for qblox-instruments <= v0.15

## \[0.16.3] - 2025-06-02

- Improved TurboCluster for faster uploads

## \[0.16.2] - 2025-05-27

- Added TurboCluster for faster uploads (Experimental!)

## \[0.16.1] - 2025-05-15

- Fix disable keyboard interrupts during communication with Cluster for Spyder 6.0.

## \[0.16.0] - 2025-05-09

- Update for qblox_instruments v0.16.0
- Changed NCO phase shift to match firmware 0.11 implementation.

## \[0.15.3] - 2025-03-26

- Better handling of keyboard interrupt when sequencer is running.

## \[0.15.2] - 2025-02-21

- Added save_program to Q1Instrument to write program to disk.

## \[0.15.1] - 2025-01-22

- Added weighed acquisition to acquire_frequency_sweep.

## \[0.15.0] - 2025-01-17

- Update to qblox-instruments 0.15.0

## \[0.14.3] - 2024-12-04

- Corrected error message waveform out of range.

## \[0.14.2] - 2024-12-04

- Check waveform data when it is added to sequencer.

## \[0.14.1] - 2024-10-17

- Dropped support for qblox-instruments < 0.11

## \[0.14.0] - 2024-10-14

- Update for qblox_instruments v0.14.1
- Fixed exception for 'out of sequencers'.
- Require Python >= 3.10

## \[0.13.0] - 2024-06-05

- Update for qblox_instruments v0.13: changed deprecated get_XXX_state to get_XXX_status

## \[0.11.11] - 2024-04-17

- Added Q1Instrument.verbose to get more logging

## \[0.11.10] - 2024-04-04

- Set sequencer label to channel name.

## \[0.11.9] - 2024-03-21

- Fixed get_input_ranges for QRM-RF module and qblox-instruments v0.11+.

## \[0.11.8] - 2024-03-21

- Fixed RF module connect in/out for qblox-instruments v0.11+.

## \[0.11.7] - 2024-03-18

- Added acquire_frequency_sweep
- Added nco_prop_delay

## \[0.11.6] - 2024-01-15

- Stop all sequencers after input overload or other error.

## \[0.11.5] - 2023-12-07

- Correct set_latch_en

## \[0.11.4] - 2023-12-06

- QUICK PATCH version for error with set_latch_en.

## \[0.11.3] - 2023-11-27

- Allow swap of IQ channels

## \[0.11.2] - 2023-10-16

- Fixed 'wait 0' bug. (Found with video mode.)

## \[0.11.1] - 2023-10-02

- Successfully tested with qblox-instruments v0.11.1

## \[0.11.0] - 2023-09-06

- Support qblox_instruments v0.11: connect_outX, connect_acq_I, connect_acq_Q
- Dropped support for qblox_instruments < v0.9.0

NOTE: 1 ns resolution of v0.10.x not yet supported.

## \[0.9.2] - 2023-07-31

- Fixed baseband qubit drive with NCO and only 1 output channel
- Improved performance of compilation with ~10%.

## \[0.9.1] - 2023-07-28

- Fixed conditionals for use with pulse-lib
- Added workaround for set_ph_delta when NCO frequency is negative (Qblox firmware bug)
- Fixed baseband qubit drive with NCO and only 1 output channel

## \[0.9.0] - 2023-07-24

- Added conditional execution of statements.
- Set AWG offsets to 0.0 after error or aborted program

## \[0.8.8] - 2023-07-11

- Generate SCPI safe waveform names.

## \[0.8.7] - 2023-06-30

- Prevent keyboard interrupt during communication with Qblox instruments.

## \[0.8.6] - 2023-06-30

- Fix bug in ramp generation.
- Check whether QCM/QRM module is present in slot.

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
