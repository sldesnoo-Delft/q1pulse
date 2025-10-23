from dataclasses import dataclass
import numpy as np

from ..lang.exceptions import Q1NameError


@dataclass
class Wave:
    name: str
    data: np.ndarray


class WaveCollection:
    def __init__(self):
        self._waves = {}

    def __getitem__(self, name):
        return self.get_wave(name)

    def get_wave(self, name):
        if name not in self._waves:
            raise Q1NameError(f'Wave {name} not defined')
        return self._waves[name]

    def add_wave(self, name, data):
        if name in self._waves:
            raise Q1NameError(f'Wave {name} already defined')
        wave = Wave(name, data)
        self._waves[name] = wave
        return wave

    def get_ramp(self, n_samples, start=0.0, stop=1.0):
        if start == 0.0 and stop == 1.0:
            name = f'_ramp_{n_samples}'
        else:
            name = f'_ramp_{n_samples}_{start*1e5:.0f}_{stop*1e5:.0f}'

        try:
            return self._waves[name]
        except KeyError:
            data = np.linspace(start, stop, n_samples, endpoint=False)
            wave = self.add_wave(name, data)
            return wave

    def get_chirp(self, n_samples, f_end, margin=0) -> tuple[Wave, Wave, float]:
        # Start with f = 0 and the delta phase / ns = 0
        # Every ns f_step/n_samples is added to delta phase / ns.
        # dp/ns = 0, 1, 2, 3, 4, ...
        # phase = 0, 1, 3, 6, 10, ...
        # phase expressed in rotations!
        dp_ns_end = f_end / 1e9
        wave_size = n_samples+margin
        dp = np.linspace(0, dp_ns_end*wave_size/n_samples, wave_size, endpoint=False)
        phase = np.cumsum(dp)
        dp_next = (phase[n_samples-1] + dp_ns_end) * 2
        nameI = f'_chirp_{n_samples}_{margin}_{f_end:.0f}_real'
        nameQ = f'_chirp_{n_samples}_{margin}_{f_end:.0f}_imag'
        try:
            return self._waves[nameI], self._waves[nameQ], dp_next
        except KeyError:
            waveI = self.add_wave(nameI, np.cos(2*np.pi*phase))
            waveQ = self.add_wave(nameQ, np.sin(2*np.pi*phase))
            # phase shift for next chirp, expressed in pi*rad!
            return waveI, waveQ, dp_next


@dataclass
class Acquisition:
    name: str
    num_bins: int


class AcquisitionCollection:
    def __init__(self):
        self._acquisitions = {}

    def __getitem__(self, name):
        return self._get_acquisition(name)

    def _get_acquisition(self, name):
        if name not in self._acquisitions:
            raise Q1NameError(f"Acquisition '{name}' not defined")
        return self._acquisitions[name]

    def add_acquisition(self, name, num_bins):
        if name in self._acquisitions:
            acquisition = self._bins[name]
            if acquisition.num_bins != num_bins:
                raise Exception(f"Inconsistent number of bins in acquisition {name}: "
                                f"{num_bins} != {acquisition.num_bins}")
        else:
            acquisition = Acquisition(name, num_bins)
            self._acquisitions[name] = acquisition
        return acquisition


@dataclass
class AcquisitionWeight:
    name: str
    data: np.ndarray


class WeightCollection:
    def __init__(self):
        self._weights = {}

    def __getitem__(self, name):
        return self.get_weight(name)

    def get_weight(self, name):
        if name not in self._weights:
            raise Q1NameError(f'Weight {name} not defined')
        return self._weights[name]

    def add_weight(self, name, data):
        if name in self._weights:
            raise Q1NameError(f'Weight {name} already defined')
        weight = AcquisitionWeight(name, data)
        self._weights[name] = weight
        return weight
