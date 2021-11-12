from .control import ControlBuilder
from .timed_statements import AcquireStatement, AcquireWeighedStatement
from .sequencer_data import (
        AcquisitionWeight, WeightCollection,
        AcquisitionBins, AcquisitionBinsCollection
        )


class ReadoutBuilder(ControlBuilder):
    def __init__(self, name, enabled_paths, nco_frequency=None):
        super().__init__(name, enabled_paths, nco_frequency)
        self._acquisitions = AcquisitionBinsCollection()
        self._weights = WeightCollection()

    def add_acquisition_bins(self, name, num_bins):
        return self._acquisitions.add_bins(name, num_bins)

    def add_weight(self, name, data):
        return self._weights.add_weight(name, data)

    def acquire(self, bins, bin_index, t_offset=0):
        section = self._translate_bins(bins)
        t1 = self.current_time + t_offset
        if bin_index == 'increment':
            reg_name = self._get_bin_reg_name(bins)
            bin_reg = self.Rs.init(reg_name)
            self._add_statement(AcquireStatement(t1, section, bin_reg))
            self.Rs[reg_name] += 1
        else:
            self._add_statement(AcquireStatement(t1, bins, bin_index))

    def acquire_weighed(self, bins, bin_index, weight0, weight1=None, t_offset=0):
        if weight1 is None:
            weight1 = weight0
        bins = self._translate_bins(bins)
        weight0 = self._translate_weight(weight0)
        weight1 = self._translate_weight(weight1)
        duration = max(
                len(weight0.data) if weight0 is not None else 0,
                len(weight1.data) if weight1 is not None else 0
                )

        with self._local_timeline(t_offset=t_offset, duration=duration):
            t1 = self.current_time
            if bin_index == 'increment':
                reg_name = self._get_bin_reg_name(bins)
                bin_reg = self.Rs.init(reg_name)
                st = AcquireWeighedStatement(t1, bins, bin_reg, weight0, weight1)
                self._add_statement(st)
                self.Rs[reg_name] += 1
            else:
                st = AcquireWeighedStatement(t1, bins, bin_index, weight0, weight1)
                self._add_statement(st)

    def reset_bin_counter(self, bins):
        reg_name = f'_bin{bins}'
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
        raise Exception(f'Illegal type {bins}')

    def _translate_weight(self, weight):
        if weight is None:
            return None
        if isinstance(weight, str):
            return self._weights[weight]
        if isinstance(weight, AcquisitionWeight):
            return weight
        raise Exception(f'Illegal type {weight}')

