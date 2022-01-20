from .control import ControlBuilder
from ..lang.exceptions import Q1ValueError, Q1TypeError
from ..lang.timed_statements import AcquireStatement, AcquireWeighedStatement
from .sequencer_data import (
        AcquisitionWeight, WeightCollection,
        AcquisitionBins, AcquisitionBinsCollection
        )


class ReadoutBuilder(ControlBuilder):
    MIN_ACQUISITION_INTERVAL = 1040

    def __init__(self, name, enabled_paths, max_output_voltage,
                 nco_frequency=None):
        super().__init__(name, enabled_paths, max_output_voltage, nco_frequency)
        self._acquisitions = AcquisitionBinsCollection()
        self._weights = WeightCollection()
        self._integration_length_acq = 4
        self._phase_rotation_acq = 0
        self._discretization_threshold_acq = 0

    @property
    def phase_rotation_acq(self):
        return self._phase_rotation_acq

    @phase_rotation_acq.setter
    def phase_rotation_acq(self, rotation):
        self._phase_rotation_acq = rotation

    @property
    def discretization_threshold_acq(self):
        return self._discretization_threshold_acq

    @discretization_threshold_acq.setter
    def discretization_threshold_acq(self, threshold):
        self._discretization_threshold_acq = threshold

    @property
    def integration_length_acq(self):
        return self._integration_length_acq

    @integration_length_acq.setter
    def integration_length_acq(self, length):
        self._integration_length_acq = int(length)

    def add_acquisition_bins(self, name, num_bins):
        return self._acquisitions.define_bins(name, num_bins)

    def add_weight(self, name, data):
        return self._weights.add_weight(name, data)

    def acquire(self, bins, bin_index='increment', t_offset=0):
        self.add_comment(f'acquire({bins}, {bin_index})')
        bins = self._translate_bins(bins)
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        # TODO Keep track of acquisition trigger interval to prevent overruns?
        if bin_index == 'increment':
            reg_name = self._get_bin_reg_name(bins)
            bin_reg = self.Rs.init(reg_name)
            self._add_statement(AcquireStatement(t1, bins, bin_reg))
            self.Rs[reg_name] += 1
        else:
            self._add_statement(AcquireStatement(t1, bins, bin_index))

    def acquire_weighed(self, bins, bin_index, weight0, weight1=None, t_offset=0):
        self.add_comment(f'acquire_weighed({bins}, {bin_index})')
        if weight1 is None:
            weight1 = weight0
        bins = self._translate_bins(bins)
        weight0 = self._translate_weight(weight0)
        weight1 = self._translate_weight(weight1)
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        if bin_index == 'increment':
            reg_name = self._get_bin_reg_name(bins)
            bin_reg = self.Rs.init(reg_name)
            st = AcquireWeighedStatement(t1, bins, bin_reg, weight0, weight1)
            self._add_statement(st)
            self.Rs[reg_name] += 1
        else:
            st = AcquireWeighedStatement(t1, bins, bin_index, weight0, weight1)
            self._add_statement(st)

    def repeated_acquire(self, n, period, bins, bin_index='increment', t_offset=0):
        self.add_comment(f'repeated_acquire({n}, {period}, {bins}, {bin_index})')
        if period < ReadoutBuilder.MIN_ACQUISITION_INTERVAL:
            raise Q1ValueError(f'Acquisition period ({period} ns) too small. '
                               f'Minimum is {ReadoutBuilder.MIN_ACQUISITION_INTERVAL} ns')
        with self._local_timeline(t_offset=t_offset, duration=(n-1)*period):
            # Repeat only n-1 times to avoid wait after last acquire.
            # A wait after the last acquire could create unwanted waits in the
            # control sequencers, because acquisition is ~100 ns delayed w.r.t. control.
            with self._seq_repeat(n-1):
                self.acquire(bins, bin_index)
                self.wait(period)
            self.acquire(bins, bin_index)

    def repeated_acquire_weighed(self, n, period, bins, bin_index,
                                 weight0, weight1=None, t_offset=0):
        self.add_comment(f'repeated_acquire_weighed({n}, {period}, {bins}, {bin_index})')
        if period < ReadoutBuilder.MIN_ACQUISITION_INTERVAL:
            raise Q1ValueError(f'Acquisition period ({period} ns) too small. '
                               f'Minimum is {ReadoutBuilder.MIN_ACQUISITION_INTERVAL} ns')
        with self._local_timeline(t_offset=t_offset, duration=(n-1)*period):
            # Repeat only n-1 times to avoid wait after last acquire.
            # A wait after the last acquire could create unwanted waits in the
            # control sequencers, because acquisition is ~100 ns delayed w.r.t. control.
            with self._seq_repeat(n-1):
                self.acquire_weighed(bins, bin_index, weight0, weight1)
                self.wait(period)
            self.acquire_weighed(bins, bin_index, weight0, weight1)

    def reset_bin_counter(self, bins):
        reg_name = self._get_bin_reg_name(bins)
        self.Rs[reg_name] = 0

    def _get_bin_reg_name(self, bins):
        if isinstance(bins, AcquisitionBins):
            return f'_bin_{bins.name}'
        return f'_bin_{bins}'

    def _translate_bins(self, bins):
        if bins is None:
            return None
        if isinstance(bins, str):
            return self._acquisitions[bins]
        if isinstance(bins, AcquisitionBins):
            return bins
        raise Q1TypeError(f'Illegal type {bins}')

    def _translate_weight(self, weight):
        if weight is None:
            return None
        if isinstance(weight, str):
            return self._weights[weight]
        if isinstance(weight, AcquisitionWeight):
            return weight
        raise Q1TypeError(f'Illegal type {weight}')

