import os
import time
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from qblox_instruments import InstrumentType
from qcodes.utils import DelayedKeyboardInterrupt

from q1pulse.program import Program
from q1pulse.lang.exceptions import Q1InputOverloaded
from q1pulse.sequencer.sequencer import SequenceBuilder
from q1pulse.sequencer.control import ControlBuilder
from q1pulse.sequencer.readout import ReadoutBuilder
from q1pulse.modules.modules import QcmModule, QrmModule
from q1pulse.util.qblox_version import check_qblox_instrument_version

logger = logging.getLogger(__name__)


class Q1Instrument:
    # Postpone error checking till the end to save communication overhead.
    # System errors are only reported for SCPI errors. It's almost impossible to
    # get an error, because everything is already checked in qblox-instruments code.
    _i_feel_lucky = True

    _exception_on_overload = True

    def __init__(self, path=None, add_traceback=True):
        check_qblox_instrument_version()
        if path:
            self.path = path
        else:
            q1dir = Path.home() / '.q1'
            q1dir.mkdir(exist_ok=True)
            self.temp_dir = TemporaryDirectory(dir=q1dir)
            self.path = self.temp_dir.name
            logger.info('Instrument upload temp dir: ' + self.path)
        self.root_instruments = set()
        self.modules = {}
        self.controllers = {}
        self.readouts = {}
        self._loaded_q1asm = {}
        SequenceBuilder.add_traceback_to_instructions = add_traceback

    def add_pulsar(self, pulsar):
        if pulsar.instrument_type == InstrumentType.QCM:
            self.add_qcm(pulsar)
        elif pulsar.instrument_type == InstrumentType.QRM:
            self.add_qrm(pulsar)
        else:
            raise Exception(f'Unknown instrument type: {pulsar.instrument_type}')

    def add_qcm(self, pulsar):
        logger.info(f'Add {pulsar.name}')
        self.modules[pulsar.name] = QcmModule(pulsar)
        self._add_root_instrument(pulsar.root_instrument)

    def add_qrm(self, pulsar):
        logger.info(f'Add {pulsar.name}')
        self.modules[pulsar.name] = QrmModule(pulsar)
        self._add_root_instrument(pulsar.root_instrument)

    def add_control(self, name, module_name, channels, nco_frequency=None):
        sequencer = self.modules[module_name].get_sequencer(channels)
        sequencer.nco_frequency = nco_frequency
        self.controllers[name] = sequencer

    def add_readout(self, name, module_name, out_channels=[],
                    nco_frequency=None, in_channels=[0,1]):
        module = self.modules[module_name]
        if not isinstance(module, QrmModule):
            raise Exception('Module {module_name} is not a QRM')
        sequencer = module.get_sequencer(out_channels)
        sequencer.nco_frequency = nco_frequency
        sequencer.in_channels = in_channels
        self.readouts[name] = sequencer

    def _add_root_instrument(self, root_instrument):
        self.root_instruments.add(root_instrument)

    def new_program(self, prog_name):
        program = Program(path=os.path.join(self.path, prog_name))
        for name, seq in self.controllers.items():
            seq_builder = ControlBuilder(name, seq.enabled_paths,
                                         seq.max_output_voltage,
                                         seq.nco_frequency)
            program.add_sequence_builder(seq_builder)

        for name, seq in self.readouts.items():
            seq_builder = ReadoutBuilder(name, seq.enabled_paths,
                                         seq.max_output_voltage,
                                         seq.nco_frequency)
            program.add_sequence_builder(seq_builder)

        return program

    def run_program(self, program):
        self.start_program(program)
        self.wait_stopped()

    def start_program(self, program):
        t_start = time.perf_counter()

        for instrument in self.root_instruments:
            with DelayedKeyboardInterrupt():
                check_instrument_status(instrument)
                if Q1Instrument._i_feel_lucky and hasattr(instrument, '_debug'):
                    # Change the debug level to speed up communication.
                    # Errors will be checked before start of the sequence.
                    instrument._debug = 2

        instruments_with_sequence = set()
        sequencers = { **self.controllers, **self.readouts }
        for name,seq in sequencers.items():
            with DelayedKeyboardInterrupt():
                module = self.modules[seq.module_name]

                q1asm = program.q1asm(name)
                self._loaded_q1asm[name] = q1asm
                if q1asm is None:
                    module.disable_seq(seq)
                    module.set_awg_offsets(seq.seq_nr, 0.0, 0.0)
                    logger.debug(f'Sequencer {name} no sequence')
                    continue
                instruments_with_sequence.add(module.pulsar.root_instrument)
                module.upload(seq.seq_nr, q1asm)
                t = (time.perf_counter() - t_start) * 1000
                # logger.debug(f'Sequencer {name} loaded ({t:5.3f} ms)')

                module.invalidate_cache(seq.seq_nr, 'offset_awg_path0')
                module.invalidate_cache(seq.seq_nr, 'offset_awg_path1')
                module.enable_seq(seq)
                prog_seq = program[name]
                module.set_nco(seq.seq_nr, prog_seq.nco_frequency)
                if prog_seq.modifies_frequency:
                    module.invalidate_cache(seq.seq_nr, 'nco_freq')
                if prog_seq.mixer_gain_ratio is not None:
                    module.set_mixer_gain_ratio(seq.seq_nr, prog_seq.mixer_gain_ratio)
                if prog_seq.mixer_phase_offset_degree is not None:
                    module.set_mixer_phase_offset_degree(seq.seq_nr, prog_seq.mixer_phase_offset_degree)
                # configure trigger counters
                for counter in prog_seq.trigger_counters:
                    module.configure_trigger_counter(seq.seq_nr, counter.trigger.address,
                                                     counter.threshold, counter.invert)

        t = (time.perf_counter() - t_start) * 1000
        # logger.debug(f'Configure QRMs ({t:5.3f} ms)')
        for name,seq in self.readouts.items():
            with DelayedKeyboardInterrupt():
                readout = program[name]
                module = self.modules[seq.module_name]
                if not module.enabled(seq.seq_nr):
                    continue
                module.thresholded_acq_rotation(seq.seq_nr, readout.thresholded_acq_rotation)
                module.thresholded_acq_threshold(seq.seq_nr, readout.thresholded_acq_threshold)
                module.integration_length_acq(seq.seq_nr, int(readout.integration_length_acq))
                module.nco_prop_delay(seq.seq_nr, int(readout.nco_prop_delay))
                module.delete_acquisition_data(seq.seq_nr)
                trigger = readout.trigger
                if trigger is not None:
                    module.set_trigger(seq.seq_nr, trigger.address, trigger.invert)
                else:
                    module.set_trigger(seq.seq_nr, None)

        with DelayedKeyboardInterrupt():
            # Note: arm per sequencer. Arm on the cluster still gives red leds on the modules.
            for module in self.modules.values():
                module.arm_sequencers()

            if Q1Instrument._i_feel_lucky:
                t = (time.perf_counter() - t_start) * 1000
                # logger.debug(f'Check status  ({t:5.3f} ms)')
                self.check_system_errors()

            for instrument in instruments_with_sequence:
                t = (time.perf_counter() - t_start) * 1000
                # logger.debug(f'Start  ({t:5.3f} ms)')
                instrument.start_sequencer()

        t = (time.perf_counter() - t_start) * 1000
        logger.info(f'Duration upload/start: ({t:5.3f}ms)')

    def wait_stopped(self, timeout_minutes=1):
        try:
            # Wait for completion
            errors = {}
            msg_level = 0
            sequencers = { **self.controllers, **self.readouts }
            for name,seq in sequencers.items():
                with DelayedKeyboardInterrupt():
                    module = self.modules[seq.module_name]
                    if not module.enabled(seq.seq_nr):
                        continue
                    state = module.get_sequencer_state(seq.seq_nr, timeout_minutes)
                    logger.log(state.level,
                                f'Status {name} ({module.pulsar.name}:{seq.seq_nr}):'
                                 f'{state}')
                    msg_level = max(msg_level, state.level)
                    if state.status != 'STOPPED' or state.level >= logging.WARNING:
                        errors[name] = str(state)
                        # reset awg offsets in case of any error.
                        module.set_awg_offsets(seq.seq_nr, 0.0, 0.0)
                    if state.input_overloaded:
                        if Q1Instrument._exception_on_overload:
                            raise Q1InputOverloaded(
                                    f'INPUT OVERLOAD on {name}.'
                                    '\nException can be suppressed with q1pulse.set_exception_on_overload(False)')
                        else:
                            print(f'WARNING: input overload on {name}')

            if msg_level == logging.ERROR:
                logger.error('*** Program errors ***')
                for name,state in errors.items():
                    logger.error(f'  {name}: {state}')
                raise Exception(f'Q1 failures (see logging):\n {errors}')
        except Exception:
            logger.error("Exception", exc_info=True)
            raise
        finally:
            with DelayedKeyboardInterrupt():
                for instrument in self.root_instruments:
                    logger.info('Stop sequencers')
                    instrument.stop_sequencer()

    def check_system_errors(self):
        for instrument in self.root_instruments:
            errors = []
            while instrument.get_num_system_error() != 0:
                errors.append(instrument.get_system_error())

            if len(errors) > 0:
                if Q1Instrument._i_feel_lucky:
                    logger.error(f"You're not lucky. One of the previous calls failed...")
                msg = instrument.name + ':' + '\n'.join(errors)
                logger.error(msg)
                raise RuntimeError(msg)

    def get_acquisition_bins(self, sequencer_name, bins):
        seq = self.readouts[sequencer_name]
        q1asm = self._loaded_q1asm[sequencer_name]
        if q1asm is None or len(q1asm['acquisitions']) == 0:
            logger.warning(f'No acquisitions for {sequencer_name}')
            return None
        module = self.modules[seq.module_name]
        with DelayedKeyboardInterrupt():
            state = module.pulsar.get_acquisition_state(seq.seq_nr, 1)
            logger.info(f'Acquisition status {sequencer_name} ({module.pulsar.name}:'
                         f'{seq.seq_nr}): {state}')
            return module.pulsar.get_acquisitions(seq.seq_nr)[bins]['acquisition']['bins']

    def get_input_ranges(self, sequencer_name):
        ''' Returns input range for both channels of sequencer.
        Value is in Vpp.
        '''
        seq = self.readouts[sequencer_name]
        module = self.modules[seq.module_name]
        in0_gain = module.pulsar.in0_gain.cache()
        in1_gain = module.pulsar.in1_gain.cache()
        in_range = tuple(
                1.0 * 10**(-dB/20)
                for dB in [in0_gain, in1_gain])
        return in_range


def set_exception_on_overload(enable:bool):
    '''
    Setting set_exception_on_overload to False suppresses Exception
    when the QRM input is overloaded.
    '''
    Q1Instrument._exception_on_overload = enable


def check_instrument_status(instrument, print_status=False):
    sys_state = instrument.get_system_state()
    if sys_state.status != 'OKAY':
        if getattr(instrument, 'is_dummy', False):
            print(f'Status (Dummy) {instrument.name}:', sys_state)
        else:
            raise Exception(f'{instrument.name} status not OKAY: {sys_state}')
