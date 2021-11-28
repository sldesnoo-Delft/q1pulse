
from ..sequencer.sequencer_data import Wave, AcquisitionBins, AcquisitionWeight


class GeneratorData:
    def __init__(self):
        self.waveforms = {}
        self.weights = {}
        self.acquisitions = {}

    def translate_waves(self, wave0, wave1):
        if wave0 is None:
            wave0 = wave1
        elif wave1 is None:
            wave1 = wave0
        return (self._translate_wave(wave0),
                self._translate_wave(wave1))

    def _translate_wave(self, wave):
        if not isinstance(wave, Wave):
            raise Exception(f'Unsupported type for wave: {wave}')

        if wave.name not in self.waveforms:
            self.waveforms[wave.name] = {
                    'data':list(wave.data),
                    'index':len(self.waveforms)
                    }

        return self.waveforms[wave.name]['index']

    def translate_acquisition(self, acquisition):
        if acquisition is None:
            return None
        if not isinstance(acquisition, AcquisitionBins):
            raise Exception(f'Unsupported type for acquisition: {acquisition}')

        if acquisition.name not in self.acquisitions:
            self.acquisitions[acquisition.name] = {
                    'num_bins': acquisition.num_bins,
                    'index': len(self.acquisitions),
                    }

        return self.acquisitions[acquisition.name]['index']

    def translate_weight(self, weight):
        if weight is None:
            return None
        if not isinstance(weight, AcquisitionWeight):
            raise Exception(f'Unsupported type for weight: {weight}')

        if weight.name not in self.weights:
            self.weights[weight.name] = {
                    'data': list(weight.data),
                    'index': len(self.weights),
                    }

        return self.weights[weight.name]['index']

    def get_data_dict(self):
        return {
                'waveforms': self.waveforms,
                'weights': self.weights,
                'acquisitions': self.acquisitions,
                }
