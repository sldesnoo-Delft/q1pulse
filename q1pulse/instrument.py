import os
import time

from .program import Program
from .sequencer.control import ControlBuilder
from .sequencer.readout import ReadoutBuilder
from .modules.modules import QcmModule, QrmModule

class Q1Instrument:
    def __init__(self, path=None, dummy=False):
        self.path = path if path is not None else 'q1'
        os.makedirs(self.path, exist_ok=True)
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
            print(f'Sequencer {name} loaded {filename} ({t:5.3f} ms)')
            module.seq_configure(seq)

        for name,seq in self.readouts.items():
            readout = program[name]
            module = self.modules[seq.module_name]
            module.phase_rotation_acq(seq.seq_nr, readout.phase_rotation_acq)
            module.discretization_threshold_acq(seq.seq_nr, readout.discretization_threshold_acq)
            module.integration_length_acq(seq.seq_nr, readout.integration_length_acq)

        for name,seq in sequencers.items():
            module = self.modules[seq.module_name]
            module.arm_sequencer(seq.seq_nr)
#            t = (time.perf_counter() - t_start) * 1000
#            print(f'ARM Status {name} ({module.pulsar.name}:{seq.seq_nr}):')
#            print(module.get_sequencer_state(seq.seq_nr, 0), f' ({t:5.3f}ms)')

        for module in self.modules.values():
            # Print an overview of the instrument parameters.
            # print(f'Snapshot {name} ({module.pulsar.name}-{seq.seq_nr}):')
            # module.pulsar.print_readable_snapshot(update=True)

            module.pulsar.start_sequencer()

        t = (time.perf_counter() - t_start) * 1000
        print(f'Duration upload/start: ({t:5.3f}ms)')
        # Wait for completion
        for name,seq in sequencers.items():
            module = self.modules[seq.module_name]
            print(f'Status {name} ({module.pulsar.name}:{seq.seq_nr}):')
            print(module.get_sequencer_state(seq.seq_nr, 1))

# TODO @@@
#            #Wait for the sequencer to stop with a timeout period of one minute.
#            pulsar.get_acquisition_state(0, 1)

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
        print(f'Acquisition status {sequencer_name} ({module.pulsar.name}:{seq.seq_nr}):')
        print(module.pulsar.get_acquisition_state(seq.seq_nr, 1))
        return module.pulsar.get_acquisitions(seq.seq_nr)[bins]['acquisition']['bins']

