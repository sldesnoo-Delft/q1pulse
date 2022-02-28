import logging
from dataclasses import dataclass
from typing import List, Optional
from abc import abstractmethod
from functools import wraps

from .sequencer_states import translate_seq_state

@dataclass
class Sequencer:
    module_name: str
    seq_nr: int
    channels: List[int]
    enabled_paths: List[int]
    max_output_voltage: float
    nco_frequency: Optional[float] = None

def requires_connection(func):
    @wraps(func)
    def func_wrapper(self, *args, **kwargs):
        if not self.pulsar:
            raise Exception(f'Module {self.name} not connected')

        return func(self, *args, **kwargs)

    return func_wrapper


class QbloxModule:
    verbose = False
    n_sequencers = 6

    def __init__(self, pulsar):
        self.name = pulsar.name
        self.pulsar = pulsar
        self._allocated_seq = 0
        self._cache = {}
        self._dont_cache = ['waveforms_and_program']

        if pulsar:
            self.check_sys_status(True)
            self.disable_all_out()
            # disable all sequencers
            for seq_nr in range(0, self.n_sequencers):
                self.enable_sync(seq_nr, False)

    @requires_connection
    def check_sys_status(self, print_status=False):
        sys_status = self.pulsar.get_system_status()
        if print_status:
            print(f'Status {self.name}:', sys_status)
        if sys_status['status'] != 'OKAY':
            raise Exception(f'Module {self.name} status not OKAY: {sys_status}')

    def get_sequencer(self, channels):
        seq_nr = self._allocate_seq_number()
        seq_paths = self._get_seq_paths(channels)
        return Sequencer(self.name, seq_nr, channels, seq_paths,
                         self.max_output_voltage)

    def _allocate_seq_number(self):
        if self._allocated_seq == self.n_sequencers:
            raise Exception(f'No more sequencers for channels {self.channels} of module {self.name}')
        sequencer_nr = self._allocated_seq
        self._allocated_seq += 1
        return sequencer_nr

    @abstractmethod
    def _get_seq_paths(self, channels):
        pass

    @requires_connection
    def disable_all_out(self):
        for seq_nr in range(0, self.n_sequencers):
            for out in range(0, self.n_channels):
                path = out % 2
                self._sset(seq_nr, f'channel_map_path{path}_out{out}_en', False)

    @requires_connection
    def upload(self, seq_nr, filename):
#        print(f'Loading {filename} to sequencer {self.pulsar.name}:{seq_nr}')
        self._sset(seq_nr, 'waveforms_and_program', filename)

    @requires_connection
    def arm_sequencer(self, seq_nr):
        self.pulsar.arm_sequencer(seq_nr)

    @requires_connection
    def get_sequencer_state(self, seq_nr, timeout=0):
        state_dict = self.pulsar.get_sequencer_state(seq_nr, timeout)
        return translate_seq_state(state_dict)

    @requires_connection
    def enable_sync(self, seq_nr, enable):
        self._sset(seq_nr, 'sync_en', enable)

    @requires_connection
    def enable_out(self, seq_nr, channel):
        path = channel % 2
        self._sset(seq_nr, f'channel_map_path{path}_out{channel}_en', True)

    @requires_connection
    def set_nco(self, seq_nr, nco_frequency):
        self._sset(seq_nr, 'mod_en_awg', nco_frequency is not None)
        if nco_frequency is not None:
            self._sset(seq_nr, 'nco_freq', nco_frequency)

    @requires_connection
    def enable_seq(self, sequencer):
        seq_nr = sequencer.seq_nr
        self.enable_sync(seq_nr, True)
        for ch in sequencer.channels:
            self.enable_out(seq_nr, ch)

    def _sset(self, seq_nr, name, value):
        full_name = f'sequencer{seq_nr}_{name}'
        current = self._cache.get(full_name, None)
        if current == value and name not in self._dont_cache:
            if QbloxModule.verbose:
                logging.debug(f'# {full_name}={value} -- cached')
            return
        result = self.pulsar.set(full_name, value)
        self._cache[full_name] = value
        if QbloxModule.verbose:
            logging.info(f'{full_name}={value}')
        return result


class QcmModule(QbloxModule):
    n_channels = 4
    max_output_voltage = 2.5

    def __init__(self, pulsar):
        super().__init__(pulsar)
        if pulsar is not None:
            type_name = type(pulsar).__name__
            if type_name not in ['pulsar_qcm', 'pulsar_qcm_dummy', 'Q1Simulator']:
                raise Exception(f'pulsar must be QCM, not {type_name}')

    def _get_seq_paths(self, channels):
        if len(channels) == 0:
            # no output, only markers
            seq_channels = []

        elif len(channels) == 1:
            channel = channels[0]
            if channel in [0, 1]:
                seq_channels = [channel]
            elif channel in [2, 3]:
                seq_channels = [channel - 2]
            else:
                raise Exception(f'illegal channel combination {channels}')

        elif len(channels) == 2:
            channel_pair = sorted(channels)
            if channel_pair == [0, 1]:
                seq_channels = channels
            elif channel_pair == [2, 3]:
                seq_channels = [ch-2 for ch in channels]
            else:
                raise Exception(f'illegal channel combination {channels}')
        else:
            raise Exception(f'illegal channel combination {channels}')

        return seq_channels


class QrmModule(QbloxModule):
    n_channels = 2
    max_output_voltage = 0.5

    def __init__(self, pulsar):
        super().__init__(pulsar)
        if pulsar is not None:
            type_name = type(pulsar).__name__
            if type_name not in ['pulsar_qrm', 'pulsar_qrm_dummy', 'Q1Simulator']:
                raise Exception(f'pulsar must be QRM, not {type_name}')

    def _get_seq_paths(self, channels):
        if len(channels) == 1:
            channel = channels[0]
            if channel not in [0, 1]:
                raise Exception(f'illegal channel combination {channels}')

        for channel in channels:
            if channel not in [0, 1]:
                raise Exception(f'illegal channel combination {channels}')

        return channels

    @requires_connection
    def seq_configure(self, sequencer):
        super().seq_configure(sequencer)

    @requires_connection
    def phase_rotation_acq(self, seq_nr, phase_rotation):
        self._sset(seq_nr, 'phase_rotation_acq', phase_rotation)

    @requires_connection
    def discretization_threshold_acq(self, seq_nr, threshold):
        self._sset(seq_nr, 'discretization_threshold_acq', threshold)

    @requires_connection
    def integration_length_acq(self, seq_nr, length):
        self._sset(seq_nr, 'integration_length_acq', length)

    @requires_connection
    def set_nco(self, seq_nr, nco_frequency):
        super().set_nco(seq_nr, nco_frequency)
        self._sset(seq_nr, 'demod_en_acq', nco_frequency is not None)

