import logging
import time
from dataclasses import dataclass
from typing import List, Optional
from abc import abstractmethod

from .sequencer_states import translate_seq_state
from ..util.qblox_version import qblox_version, Version

logger = logging.getLogger(__name__)

@dataclass
class Sequencer:
    module_name: str
    seq_nr: int
    channels: List[int]
    enabled_paths: List[int]
    max_output_voltage: float
    nco_frequency: Optional[float] = None


class QbloxModule:
    verbose = False
    n_sequencers = 6

    def __init__(self, pulsar):
        self.name = pulsar.name
        # check module is present in slot.
        if hasattr(pulsar, 'present'):
            if not pulsar.present():
                raise Exception('No module in slot {pulsar.slot_idx}')
        self.pulsar = pulsar
        self._allocated_seq = 0
        self.disable_all_out()
        # disable all sequencers
        for seq_nr in range(0, self.n_sequencers):
            self.enable_sync(seq_nr, False)

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

    def disable_all_out(self):
        for seq_nr in range(0, self.n_sequencers):
            for out in range(0, self.n_channels):
                if qblox_version < Version('0.11'):
                    path = out % 2
                    self._sset(seq_nr, f'channel_map_path{path}_out{out}_en', False)
                else:
                    self._sset(seq_nr, f'connect_out{out}', 'off')

    def upload(self, seq_nr, sequence):
        if isinstance(sequence, str):
            # don't cache sequence. The contents of the file might have changed.
            filename = sequence
            # print(f'Loading {filename} to sequencer {self.pulsar.name}:{seq_nr}')
            self._sset(seq_nr, 'sequence', filename, cache=False)
        else:
            self._sset(seq_nr, 'sequence', sequence)

    def arm_sequencers(self):
        for seq_nr in range(0, self.n_sequencers):
            if self.enabled(seq_nr):
                self.pulsar.arm_sequencer(seq_nr)

    def start_sequencers(self):
        enabled = [self.enabled(seq_nr) for seq_nr in range(0, self.n_sequencers)]
        if any(enabled):
            self.pulsar.start_sequencer()

    def stop_sequencers(self):
        self.pulsar.stop_sequencer()

    def get_sequencer_state(self, seq_nr, timeout=0):
        state = self.pulsar.get_sequencer_state(seq_nr, timeout)
        return translate_seq_state(state)

    def enable_sync(self, seq_nr, enable):
        self._sset(seq_nr, 'sync_en', enable)

    def enable_out(self, seq_nr, channel):
        if qblox_version < Version('0.11'):
            path = channel % 2
            self._sset(seq_nr, f'channel_map_path{path}_out{channel}_en', True)
        else:
            # Keep old convention: I on 0 and 2, Q on 1 and 3
            # TODO: change API to allow different IQ mapping.
            value = 'I' if channel  % 2 == 0 else 'Q'
            self._sset(seq_nr, f'connect_out{channel}', value)

    def set_nco(self, seq_nr, nco_frequency):
        self._sset(seq_nr, 'mod_en_awg', nco_frequency is not None)
        if nco_frequency is not None:
            self._sset(seq_nr, 'nco_freq', nco_frequency)

    def set_mixer_gain_ratio(self, seq_nr, value):
        self._sset(seq_nr, 'mixer_corr_gain_ratio', value)

    def set_mixer_phase_offset_degree(self, seq_nr, value):
        self._sset(seq_nr, 'mixer_corr_phase_offset_degree', value)

    def configure_trigger_counter(self, seq_nr, address, threshold, invert):
        self._sset(seq_nr, f'trigger{address}_count_threshold', threshold)
        self._sset(seq_nr, f'trigger{address}_threshold_invert', invert)

    def set_awg_offsets(self, seq_nr, offset0, offset1):
        self._sset(seq_nr, f'offset_awg_path0', offset0)
        self._sset(seq_nr, f'offset_awg_path1', offset1)

    def enabled(self, seq_nr):
        seq = getattr(self.pulsar, f'sequencer{seq_nr}')
        param = seq.parameters['sync_en']
        return param.cache()

    def disable_seq(self, sequencer):
        seq_nr = sequencer.seq_nr
        self.enable_sync(seq_nr, False)

    def enable_seq(self, sequencer):
        seq_nr = sequencer.seq_nr
        self.enable_sync(seq_nr, True)
        for ch in sequencer.channels:
            self.enable_out(seq_nr, ch)

    def _sset(self, seq_nr, name, value, cache=True):
        full_name = f'sequencer{seq_nr}.{name}'
        seq = getattr(self.pulsar, f'sequencer{seq_nr}')
        param = seq.parameters[name]
        try:
            if cache and param.cache.valid and param.cache() == value:
                if QbloxModule.verbose:
                    logger.debug(f'# {full_name}={value} -- cached')
                return
        except:
            logger.debug(f'No cache value for {full_name}')
        result = param(value)
        if QbloxModule.verbose:
            logger.info(f'{full_name}={value}')
        return result

    def invalidate_cache(self, seq_nr, param_name):
        seq = getattr(self.pulsar, f'sequencer{seq_nr}')
        param = seq.parameters[param_name]
        param.cache.invalidate()

    def set_out_offset(self, channel, offset_mV):
        if self.pulsar.is_rf_type:
            name = f'out{channel//2}_offset_path{channel%2}'
            value = offset_mV
        else:
            name = f'out{channel}_offset'
            value = offset_mV/1000

        param = self.pulsar.parameters[name]
        if param.cache() == value:
            if QbloxModule.verbose:
                logger.debug(f'# {name}={value} -- cached')
            return
        param(value)


class QcmModule(QbloxModule):
    n_channels = 4

    def __init__(self, pulsar):
        super().__init__(pulsar)
        self.max_output_voltage = 2.5 if not pulsar.is_rf_type else 3.3

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

    def __init__(self, pulsar):
        super().__init__(pulsar)
        self.max_output_voltage = 0.5 if not pulsar.is_rf_type else 3.3
        ### Do not start calibration. It is not reliable!
        # self._start_adc_calibration()

    def _start_adc_calibration(self):
        if qblox_version >= Version('0.8') and qblox_version < Version('0.9'):
            # A short sleep before starting calibration avoids calibration failures...
            time.sleep(0.1)
            logger.info(f'Calibrating QRM {self.name}')
            try:
                pulsar = self.pulsar
                if hasattr(pulsar, 'start_adc_calib'):
                    pulsar.start_adc_calib()
                else:
                    pulsar.root_instrument.start_adc_calib(pulsar.slot_idx)
            except Exception as ex:
                logger.warning('Calibration of QRM failed', ex)

    def _get_seq_paths(self, channels):
        for channel in channels:
            if channel not in [0, 1]:
                raise Exception(f'illegal channel combination {channels}')

        return channels

    def thresholded_acq_rotation(self, seq_nr, phase_rotation):
        if qblox_version < Version('0.9'):
            # v0.8.x
            self._sset(seq_nr, 'phase_rotation_acq', phase_rotation)
        else:
            self._sset(seq_nr, 'thresholded_acq_rotation', phase_rotation)

    def thresholded_acq_threshold(self, seq_nr, threshold):
        if qblox_version < Version('0.9'):
            # v0.8.x
            self._sset(seq_nr, 'discretization_threshold_acq', threshold)
        else:
            self._sset(seq_nr, 'thresholded_acq_threshold', threshold)

    def integration_length_acq(self, seq_nr, length):
        self._sset(seq_nr, 'integration_length_acq', length)

    def delete_acquisition_data(self, seq_nr):
        self.pulsar.delete_acquisition_data(seq_nr, all=True)

    def set_nco(self, seq_nr, nco_frequency):
        super().set_nco(seq_nr, nco_frequency)
        self._sset(seq_nr, 'demod_en_acq', nco_frequency is not None)

    def set_trigger(self, seq_nr, address, invert=False):
        enabled = address is not None and address > 0
        self._sset(seq_nr, 'thresholded_acq_trigger_en', enabled)
        if enabled:
            self._sset(seq_nr, 'thresholded_acq_trigger_address', address)
            self._sset(seq_nr, 'thresholded_acq_trigger_invert', invert)

