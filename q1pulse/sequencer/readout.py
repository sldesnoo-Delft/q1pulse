from .control import ControlBuilder
from ..lang.exceptions import Q1ValueError, Q1TypeError
from ..lang.timed_statements import AcquireStatement, AcquireWeighedStatement, AcquireTtlStatement
from .sequencer_data import (
    AcquisitionWeight, WeightCollection,
    Acquisition, AcquisitionCollection
)


class ReadoutBuilder(ControlBuilder):
    MIN_ACQUISITION_INTERVAL = 300

    def __init__(self, name, enabled_paths, max_output_voltage,
                 nco_frequency=None):
        super().__init__(name, enabled_paths, max_output_voltage, nco_frequency)
        self._acquisitions = AcquisitionCollection()
        self._weights = WeightCollection()
        self._integration_length_acq = 4
        self._thresholded_acq_rotation = 0.0
        self._thresholded_acq_threshold = 0.0
        self._trigger = None
        self._nco_prop_delay = 0
        self._ttl_acq_input_select = None
        self._ttl_acq_auto_bin_incr_en = None
        self._ttl_acq_threshold = None

    @property
    def thresholded_acq_rotation(self):
        return self._thresholded_acq_rotation

    @thresholded_acq_rotation.setter
    def thresholded_acq_rotation(self, rotation):
        self._thresholded_acq_rotation = rotation

    @property
    def thresholded_acq_threshold(self):
        return self._thresholded_acq_threshold

    @thresholded_acq_threshold.setter
    def thresholded_acq_threshold(self, threshold):
        self._thresholded_acq_threshold = threshold

    @property
    def integration_length_acq(self):
        return self._integration_length_acq

    @integration_length_acq.setter
    def integration_length_acq(self, length):
        self._integration_length_acq = int(length)

    @property
    def nco_prop_delay(self):
        return self._nco_prop_delay

    @nco_prop_delay.setter
    def nco_prop_delay(self, delay):
        self._nco_prop_delay = delay

    @property
    def trigger(self):
        return self._trigger

    @trigger.setter
    def trigger(self, trigger):
        self._trigger = trigger

    @property
    def ttl_acq_input_select(self):
        return self._ttl_acq_input_select

    @ttl_acq_input_select.setter
    def ttl_acq_input_select(self, value):
        self._ttl_acq_input_select = value

    @property
    def ttl_acq_auto_bin_incr_en(self):
        return self._ttl_acq_auto_bin_incr_en

    @ttl_acq_auto_bin_incr_en.setter
    def ttl_acq_auto_bin_incr_en(self, enable):
        self._ttl_acq_auto_bin_incr_en = enable

    @property
    def ttl_acq_threshold(self):
        return self._ttl_acq_threshold

    @ttl_acq_threshold.setter
    def ttl_acq_threshold(self, threshold):
        self._ttl_acq_threshold = threshold

    def add_acquisition_bins(self, name, num_bins):
        return self._acquisitions.add_acquisition(name, num_bins)

    def add_weight(self, name, data):
        return self._weights.add_weight(name, data)

    def acquire(self, acquisition, bin_index='increment', t_offset=0):
        self.add_comment(f'acquire({acquisition}, {bin_index})')
        acquisition = self._translate_acquisition(acquisition)
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        # TODO Keep track of acquisition trigger interval to prevent overruns?
        if bin_index == 'increment':
            reg_name = self._get_acquisition_reg_name(acquisition)
            bin_reg = self.Rs.init(reg_name)
            self._add_statement(AcquireStatement(t1, acquisition, bin_reg))
            self.Rs[reg_name] += 1
        else:
            self._add_statement(AcquireStatement(t1, acquisition, bin_index))

    def acquire_weighed(self, acquisition, bin_index, weight0, weight1=None, t_offset=0):
        self.add_comment(f'acquire_weighed({acquisition}, {bin_index})')
        if weight1 is None:
            weight1 = weight0
        acquisition = self._translate_acquisition(acquisition)
        weight0 = self._translate_weight(weight0)
        weight1 = self._translate_weight(weight1)
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        if bin_index == 'increment':
            reg_name = self._get_acquisition_reg_name(acquisition)
            bin_reg = self.Rs.init(reg_name)
            st = AcquireWeighedStatement(t1, acquisition, bin_reg, weight0, weight1)
            self._add_statement(st)
            self.Rs[reg_name] += 1
        else:
            st = AcquireWeighedStatement(t1, acquisition, bin_index, weight0, weight1)
            self._add_statement(st)

    def acquire_ttl(self, acquisition, bin_index, enable, t_offset=0):
        self.add_comment(f'acquire_ttl({acquisition}, {bin_index}, {enable})')
        acquisition = self._translate_acquisition(acquisition)
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        if bin_index == 'increment':
            if enable:
                reg_name = self._get_acquisition_reg_name(acquisition)
                bin_reg = self.Rs.init(reg_name)
                self._add_statement(AcquireTtlStatement(t1, acquisition, bin_reg, enable))
                self.Rs[reg_name] += 1
            else:
                self._add_statement(AcquireTtlStatement(t1, acquisition, 0, enable))
        else:
            self._add_statement(AcquireTtlStatement(t1, acquisition, bin_index, enable))

    def repeated_acquire(self, n, period, acquisition, bin_index='increment', t_offset=0):
        self.add_comment(f'repeated_acquire({n}, {period}, {acquisition}, {bin_index})')
        if period < ReadoutBuilder.MIN_ACQUISITION_INTERVAL:
            raise Q1ValueError(f'Acquisition period ({period} ns) too small. '
                               f'Minimum is {ReadoutBuilder.MIN_ACQUISITION_INTERVAL} ns')
        with self._local_timeline(t_offset=t_offset, duration=(n-1)*period):
            # Repeat only n-1 times to avoid wait after last acquire.
            # A wait after the last acquire could create unwanted waits in the
            # control sequencers, because acquisition is ~100 ns delayed w.r.t. control.
            if n > 1:
                with self._seq_repeat(n-1):
                    self.acquire(acquisition, bin_index)
                    self.wait(period)
            self.acquire(acquisition, bin_index)

    def acquire_frequency_sweep(self, n, period,
                                f_start, f_stop,
                                acquisition,
                                bin_index='increment',
                                acq_delay=0,
                                weight0: str | AcquisitionWeight | None = None,
                                weight1: str | AcquisitionWeight | None = None,
                                t_offset: int = 0):
        """
        Aquire `n` values with interval `period` while stepping frequency from `f_start` till `f_stop`.

        Args:
            n: number of values to acquire
            period: time between acquisitions
            f_start: start frequency
            f_stop: stop frequency, inclusive
            acq_delay: delay between changing frequency and starting acquisition
            weight0: if not None use weighed accquisition with specified weight for path 0.
            weight1: if not None use weighed accquisition with specified weight for path 1.
        Note:
            Experimentally it is determined that the nco_prop_delay should be 146 ns + delay in lines (~ 4 ns/m),
            and acq_delay should be nco_prop_delay + 4 ns.
        """
        self.add_comment(f'acquire_frequency_sweep({n}, {period}, {f_start}, {f_stop} {acquisition}, {bin_index})')
        if period < ReadoutBuilder.MIN_ACQUISITION_INTERVAL:
            raise Q1ValueError(f'Acquisition period ({period} ns) too small. '
                               f'Minimum is {ReadoutBuilder.MIN_ACQUISITION_INTERVAL} ns')
        if acq_delay > period - 20:
            raise Q1ValueError(f"acq_delay ({acq_delay}) too big. It should be less than period ({period}) - 20")

        with self._local_timeline(t_offset=t_offset, duration=(n-1)*period):
            # Repeat only n-1 times to avoid wait after last acquire.
            # A wait after the last acquire could create unwanted waits in the
            # control sequencers, because acquisition is ~100 ns delayed w.r.t. control.
            f_step = (f_stop - f_start) / (n - 1)
            self.Rs.frequency = int(f_start)
            self.set_frequency(self.Rs.frequency)
            self.wait(acq_delay)
            if n > 1:
                with self._seq_repeat(n-1):
                    if weight0 is not None or weight1 is not None:
                        self.acquire_weighed(acquisition, bin_index, weight0, weight1)
                    else:
                        self.acquire(acquisition, bin_index)
                    self.Rs.frequency += int(f_step)
                    self.wait(period - acq_delay)
                    self.set_frequency(self.Rs.frequency)
                    self.wait(acq_delay)
            if weight0 is not None or weight1 is not None:
                self.acquire_weighed(acquisition, bin_index, weight0, weight1)
            else:
                self.acquire(acquisition, bin_index)

    def repeated_acquire_weighed(self, n, period, acquisition, bin_index,
                                 weight0, weight1=None, t_offset=0):
        self.add_comment(f'repeated_acquire_weighed({n}, {period}, {acquisition}, {bin_index})')
        if period < ReadoutBuilder.MIN_ACQUISITION_INTERVAL:
            raise Q1ValueError(f'Acquisition period ({period} ns) too small. '
                               f'Minimum is {ReadoutBuilder.MIN_ACQUISITION_INTERVAL} ns')
        with self._local_timeline(t_offset=t_offset, duration=(n-1)*period):
            # Repeat only n-1 times to avoid wait after last acquire.
            # A wait after the last acquire could create unwanted waits in the
            # control sequencers, because acquisition is ~100 ns delayed w.r.t. control.
            if n > 1:
                with self._seq_repeat(n-1):
                    self.acquire_weighed(acquisition, bin_index, weight0, weight1)
                    self.wait(period)
            self.acquire_weighed(acquisition, bin_index, weight0, weight1)

    def acquire_ttl_interval(self, acquisition, bin_index, duration, t_offset=0):
        """Perform TTL acquisition for specified duration.
        """
        with self._local_timeline(t_offset=t_offset, duration=duration):
            self.acquire_ttl(acquisition, bin_index, 1)
            self.wait(duration)
            self.acquire_ttl(acquisition, bin_index, 0)

    def reset_bin_counter(self, acquisition):
        reg_name = self._get_acquisition_reg_name(acquisition)
        self.Rs[reg_name] = 0

    def _get_acquisition_reg_name(self, acquisition):
        if isinstance(acquisition, Acquisition):
            return f'_acq_{acquisition.name}'
        return f'_acq_{acquisition}'

    def _translate_acquisition(self, acquisition):
        if acquisition is None:
            return None
        if isinstance(acquisition, str):
            return self._acquisitions[acquisition]
        if isinstance(acquisition, Acquisition):
            return acquisition
        raise Q1TypeError(f'Illegal type {acquisition}')

    def _translate_weight(self, weight):
        if weight is None:
            return None
        if isinstance(weight, str):
            return self._weights[weight]
        if isinstance(weight, AcquisitionWeight):
            return weight
        raise Q1TypeError(f'Illegal type {weight}')
