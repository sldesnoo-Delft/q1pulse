import os

from .program import Program
from .model.control import ControlBuilder
from .model.readout import ReadoutBuilder
from .modules.modules import QcmModule, QrmModule

class QbInstrument:
    def __init__(self, path=None, dummy=False):
        self.path = path if path is not None else 'q1'
        self._dummy = dummy
        os.makedirs(self.path, exist_ok=True)
        self.modules = {}
        self.controllers = {}
        self.readouts = {}

    def add_qcm(self, module_nr, ip_addr):
        self.modules[module_nr] = QcmModule(module_nr, ip_addr, dummy=self._dummy)

    def add_qrm(self, module_nr, ip_addr):
        self.modules[module_nr] = QrmModule(module_nr, ip_addr, dummy=self._dummy)

    def add_control(self, name, module_nr, channels, lo_frequency=None):
        sequencer = self.modules[module_nr].get_sequencer(channels)
        sequencer.lo_frequency = lo_frequency
        self.controllers[name] = sequencer

    def add_readout(self, name, module_nr, out_channels=[], lo_frequency=None):
        module = self.modules[module_nr]
        if not isinstance(module, QrmModule):
            raise Exception('Module {module_nr} is not a QRM')
        sequencer = module.get_sequencer(out_channels)
        sequencer.lo_frequency = lo_frequency
        self.readouts[name] = sequencer

    def new_program(self, prog_name):
        sequence_builders = {}
        for name, sequencer in self.controllers.items():
            # @@@ add lo_frequency
            sequence_builders[name] = ControlBuilder(name, sequencer.enabled_paths)

        for name, sequencer in self.readouts.items():
            # @@@ add lo_frequency
            sequence_builders[name] = ReadoutBuilder(name, sequencer.enabled_paths)

        return Program(sequence_builders, path=os.path.join(self.path, prog_name))

    def connect(self):
        for module in self.modules.values():
            module.connect()

    def run_program(self, program):
        sequencers = { **self.controllers, **self.readouts }
        for module in self.modules.values():
            module.disable_all_out()
        for name,seq in sequencers.items():
            module = self.modules[seq.module_nr]

            filename = program.seq_filename(name)
            print(f'Sequencer {name} loading {filename}')
            module.upload(seq.seq_nr, filename)
            module.seq_configure(seq)
            module.arm_sequencer(seq.seq_nr)

            # Print an overview of the instrument parameters.
            print("Snapshot:")
            module.pulsar.print_readable_snapshot(update=True)

        for module in self.modules.values():
            module.pulsar.start_sequencer()

        # Wait for completion
        for name,seq in sequencers.items():
            module = self.modules[seq.module_nr]
            print("Status:")
            print(module.get_sequencer_state(0, 1))

# TODO @@@
#            #Wait for the sequencer to stop with a timeout period of one minute.
#            pulsar.get_acquisition_state(0, 1)

        for name,seq in sequencers.items():
            module = self.modules[seq.module_nr]
            #Stop sequencer.
            module.pulsar.stop_sequencer()

# TODO @@@
#    def close(self):
#        #Close the instrument connection.
#        pulsar.close()
