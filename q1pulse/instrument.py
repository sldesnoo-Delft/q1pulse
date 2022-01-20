import os
import time
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from .program import Program
from .sequencer.control import ControlBuilder
from .sequencer.readout import ReadoutBuilder
from .modules.modules import QcmModule, QrmModule

class Q1Instrument:
    def __init__(self, path=None, dummy=False):
        if path:
            self.path = path
        else:
            q1dir = Path.home() / '.q1'
            q1dir.mkdir(exist_ok=True)
            self.temp_dir = TemporaryDirectory(dir=q1dir)
            self.path = self.temp_dir.name
            logging.info('Instrument upload temp dir: ' + self.path)
        self.modules = {}
        self.controllers = {}
        self.readouts = {}

    def add_qcm(self, pulsar):
        self.modules[pulsar.name] = QcmModule(pulsar)

    def add_qrm(self, pulsar):
        self.modules[pulsar.name] = QrmModule(pulsar)

    def add_control(self, name, module_name, channels, nco_frequency=None):
        sequencer = self.modules[module_name].get_sequencer(channels)
        sequencer.nco_frequency = nco_frequency
        self.controllers[name] = sequencer

    def add_readout(self, name, module_name, out_channels=[], nco_frequency=None):
        module = self.modules[module_name]
        if not isinstance(module, QrmModule):
            raise Exception('Module {module_name} is not a QRM')
        sequencer = module.get_sequencer(out_channels)
        sequencer.nco_frequency = nco_frequency
        self.readouts[name] = sequencer

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
        t_start = time.perf_counter()

        # @@@ program sequence builders
        sequencers = { **self.controllers, **self.readouts }
        for name,seq in sequencers.items():
            module = self.modules[seq.module_name]

            filename = program.seq_filename(name)
            module.upload(seq.seq_nr, filename)
            t = (time.perf_counter() - t_start) * 1000
            logging.info(f'Sequencer {name} loaded {filename} ({t:5.3f} ms)')
            module.seq_configure(seq)

        for name,seq in self.readouts.items():
            readout = program[name]
            module = self.modules[seq.module_name]
            module.phase_rotation_acq(seq.seq_nr, readout.phase_rotation_acq)
            module.discretization_threshold_acq(seq.seq_nr, readout.discretization_threshold_acq)
            module.integration_length_acq(seq.seq_nr, int(readout.integration_length_acq))

        for name,seq in sequencers.items():
            module = self.modules[seq.module_name]
            module.arm_sequencer(seq.seq_nr)
            t = (time.perf_counter() - t_start) * 1000
            state = module.get_sequencer_state(seq.seq_nr, 0)
#            logging.debug(f'ARM Status {name} ({module.pulsar.name}:{seq.seq_nr}):'
#                          f'{state} ({t:5.3f}ms)')

        for module in self.modules.values():
            # Print an overview of the instrument parameters.
            # print(f'Snapshot {name} ({module.pulsar.name}-{seq.seq_nr}):')
            # module.pulsar.print_readable_snapshot(update=True)
            module.pulsar.start_sequencer()

        t = (time.perf_counter() - t_start) * 1000
        logging.info(f'Duration upload/start: ({t:5.3f}ms)')
        # Wait for completion
        errors = {}
        for name,seq in sequencers.items():
            module = self.modules[seq.module_name]
            state = module.get_sequencer_state(seq.seq_nr, 1)
            logging.info(f'Status {name} ({module.pulsar.name}:{seq.seq_nr}):'
                         f'{state}')
            if (state['status'] != 'STOPPED'
                or (state['flags'] != []
                    and state['flags'] != ['ACQ BINNING DONE'])):
                errors[seq.module_name] = state
        if len(errors):
            logging.error('*** Program errors ***')
            for name,state in errors.items():
                logging.error(f'  {name}: {state}')
            raise Exception(f'Q1 failures (see logging):\n {errors}')

        for name,seq in sequencers.items():
            module = self.modules[seq.module_name]
            #Stop sequencer.
            module.pulsar.stop_sequencer()

# TODO @@@
#    def close(self):
#        #Close the instrument connection.
#        pulsar.close()

    def get_acquisition_bins(self, sequencer_name, bins):
        seq = self.readouts[sequencer_name]
        module = self.modules[seq.module_name]
        state = module.pulsar.get_acquisition_state(seq.seq_nr, 1)
        logging.info(f'Acquisition status {sequencer_name} ({module.pulsar.name}:'
                     f'{seq.seq_nr}): {state}')
        return module.pulsar.get_acquisitions(seq.seq_nr)[bins]['acquisition']['bins']

    def get_input_ranges(self, sequencer_name):
        ''' Returns input range for both channels of sequencer.
        Value is in Vpp.
        '''
        seq = self.readouts[sequencer_name]
        module = self.modules[seq.module_name]
#        in0_gain = module.pulsar.in0_gain.cache()
#        in1_gain = module.pulsar.in1_gain.cache()
        in0_gain = module.pulsar.in0_gain()
        in1_gain = module.pulsar.in1_gain()
        in_range = tuple(
                1.0 * 10**(-dB/20)
                for dB in [in0_gain, in1_gain])
        return in_range

