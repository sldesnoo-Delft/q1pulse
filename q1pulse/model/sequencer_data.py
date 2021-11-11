from dataclasses import dataclass
import numpy as np

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
            raise Exception(f'Wave {name} not defined')
        return self._waves[name]

    def add_wave(self, name, data):
        if name in self._waves:
            raise Exception(f'Wave {name} already defined')
        wave = Wave(name, data)
        self._waves[name] = wave
        return wave

    def get_ramp(self, n_samples, start=0.0, stop=1.0):
        if start == 0.0 and stop == 1.0:
            name = f'_ramp({n_samples})'
        else:
            name = f'_ramp({n_samples}, {start:5.3f}, {stop:5.3f})'

        try:
            return self._waves[name]
        except:
            data = np.linspace(start, stop, n_samples, endpoint=False)
            wave = self.add_wave(name, data)
            return wave


@dataclass
class AcquisitionSection:
    name: str
    num_bins: int

class AcquisitionSections:
    def __init__(self):
        self._sections = {}

    def __getitem__(self, name):
        return self._get_section(name)

    def _get_section(self, name):
        if name not in self._sections:
            raise Exception(f'Acquisition {name} not defined')
        return self._waves[name]

    def add_section(self, name, num_bins):
        if name in self._sections:
            raise Exception(f'Acquisition {name} already defined')
        section = AcquisitionSection(name, num_bins)
        self._sections[name] = section
        return section
