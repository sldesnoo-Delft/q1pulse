from dataclasses import dataclass
from typing import List, Optional
from abc import abstractmethod
from functools import wraps

from pulsar_qcm.pulsar_qcm import pulsar_qcm, pulsar_qcm_dummy
from pulsar_qrm.pulsar_qrm import pulsar_qrm, pulsar_qrm_dummy

@dataclass
class Sequencer:
    module_nr: int
    seq_nr: int
    channels: List[int]
    enabled_paths: List[int]
    lo_frequency: Optional[float] = None

def requires_connection(func):
    @wraps(func)
    def func_wrapper(self, *args, **kwargs):
        if not self.pulsar:
            raise Exception(f'Module {self.module_nr} not connected')

        return func(self, *args, **kwargs)

    return func_wrapper


class QbloxModule:
    n_sequencers = 6

    def __init__(self, module_nr, ip_addr, dummy=False):
        self.module_nr = module_nr
        self.ip_addr = ip_addr
        self._use_dummy = dummy
        self._allocated_seq = 0
        self.pulsar = None

    def get_sequencer(self, channels):
        seq_nr = self._allocate_seq_number()
        seq_paths = self._get_seq_paths(channels)
        return Sequencer(self.module_nr, seq_nr, channels, seq_paths)

    def _allocate_seq_number(self):
        if self._allocated_seq == self.n_sequencers:
            raise Exception(f'No more sequencers for channels {self.channels} of module {self.module_nr}')
        sequencer_nr = self._allocated_seq
        self._allocated_seq += 1
        return sequencer_nr

    @abstractmethod
    def _get_seq_paths(self, channels):
        pass

    @abstractmethod
    def connect(self):
        pass

    @requires_connection
    def disable_all_out(self):
        for seq_nr in range(0, self.n_sequencers):
            for out in range(0, self.n_channels):
                path = out % 2
                self.__sset(seq_nr, f'channel_map_path{path}_out{out}_en', False)

    @requires_connection
    def upload(self, seq_nr, filename):
        print(f'Loading {filename} to sequencer {seq_nr}')
        self.__sset(seq_nr, 'waveforms_and_program', filename)

    @requires_connection
    def arm_sequencer(self, seq_nr):
        self.pulsar.arm_sequencer(seq_nr)

    @requires_connection
    def get_sequencer_state(self, seq_nr, timeout):
        return self.pulsar.get_sequencer_state(seq_nr, timeout)

    @requires_connection
    def enable_sync(self, seq_nr, enable):
        self.__sset(seq_nr, 'sync_en', enable)

    @requires_connection
    def enable_out(self, seq_nr, channel):
        path = channel % 2
        self.__sset(seq_nr, f'channel_map_path{path}_out{channel}_en', True)

    @requires_connection
    def set_nco(self, seq_nr, lo_frequency):
        self.__sset(seq_nr, 'mod_en_awg', lo_frequency is not None)
        if lo_frequency is not None:
            self.__sset(seq_nr, 'nco_freq', lo_frequency)

    @requires_connection
    def seq_configure(self, sequencer):
        seq_nr = sequencer.seq_nr
        self.enable_sync(seq_nr, True)
        self.set_nco(seq_nr, sequencer.lo_frequency)
        for ch in sequencer.channels:
            self.enable_out(seq_nr, ch)

    def __sset(self, seq_nr, name, value):
        return self.pulsar.set(f'sequencer{seq_nr}_{name}', value)


class QcmModule(QbloxModule):
    n_channels = 4

    def __init__(self, number, ip_addr, dummy=False):
        super().__init__(number, ip_addr, dummy)

    def _get_seq_paths(self, channels):
        if len(channels) == 1:
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

    def connect(self):
        if self.pulsar is not None:
            print(f'Pulsar {self.module_nr} already connected')
            return

        if self._use_dummy:
            print(f'Starting QCM qcm_{self.module_nr} dummy')
            pulsar = pulsar_qcm_dummy(f'qcm_{self.module_nr}')
        else:
            print(f'Connecting Pulsar {self.module_nr} on {self.ip_addr}...')
            pulsar = pulsar_qcm(f'qcm_{self.module_nr}', self.ip_addr)
        # Reset the instrument for good measure.
        pulsar.reset()
        print("Status:", pulsar.get_system_status())

        self.pulsar = pulsar


class QrmModule(QbloxModule):
    n_channels = 2

    def __init__(self, number, ip_addr, dummy=False):
        super().__init__(number, ip_addr, dummy)

    def _get_seq_paths(self, channels):
        if len(channels) == 2:
            raise Exception(f'illegal channel combination {channels}')

        for channel in channels:
            if channel not in [0, 1]:
                raise Exception(f'illegal channel combination {channels}')

        return channels

    def connect(self):

        if self.pulsar is not None:
            print(f'Pulsar {self.module_nr} already connected')
            return

        if self._use_dummy:
            print(f'Starting QRM qrm_{self.module_nr} dummy')
            pulsar = pulsar_qrm_dummy(f'qrm_{self.module_nr}')
        else:
            print(f'Connecting Pulsar {self.module_nr} on {self.ip_addr}...')
            pulsar = pulsar_qrm(f'qrm_{self.module_nr}', self.ip_addr)
        # Reset the instrument for good measure.
        pulsar.reset()
        print("Status:", pulsar.get_system_status())

        self.pulsar = pulsar

    @requires_connection
    def set_nco(self, seq_nr, lo_frequency):
        super().set_nco(seq_nr, lo_frequency)
        self.__sset(seq_nr, 'demod_en_acq', lo_frequency is not None)

    def __sset(self, seq_nr, name, value):
        return self.pulsar.set(f'sequencer{seq_nr}_{name}', value)


## TODO @@@
##Configure scope mode
#pulsar.scope_acq_sequencer_select(0)
#pulsar.scope_acq_trigger_mode_path0("sequencer")
#pulsar.scope_acq_trigger_mode_path1("sequencer")

##Configure the sequencer
#pulsar.sequencer0_integration_length_acq(1000)
#pulsar.sequencer0_phase_rotation_acq(0)
#pulsar.sequencer0_discretization_threshold_acq(0)

