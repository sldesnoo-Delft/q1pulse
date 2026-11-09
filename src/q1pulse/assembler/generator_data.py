from q1pulse.sequencer.sequencer_data import Wave, Acquisition, AcquisitionWeight
from q1pulse.lang.exceptions import Q1TypeError, Q1MemoryError
from q1pulse.util.q1configuration import Q1Configuration


class GeneratorData:
    def __init__(self):
        self.waveforms = {}
        self.weights = {}
        self.acquisitions = {}
        self._size_waveforms = 0
        self._size_weights = 0

    def translate_wave(self, wave: Wave):
        if not isinstance(wave, Wave):
            raise Q1TypeError(f'Unsupported type for wave: {wave}')

        waveforms = self.waveforms
        try:
            entry = waveforms[wave.name]
            return entry['index']
        except KeyError:
            index = len(waveforms)
            if index >= Q1Configuration.MAX_NUM_WAVEFORMS - 1:
                raise Q1MemoryError("Too many waveforms")
            size_waveforms = self._size_waveforms + len(wave.data)
            if size_waveforms > Q1Configuration.WAVEFORM_MEM_SIZE:
                raise Q1MemoryError("Too much waveform data for memory")
            self._size_waveforms = size_waveforms
            waveforms[wave.name] = {
                    'data': wave.data.tolist(),
                    'index': index
                    }
            return index

    def translate_acquisition(self, acquisition):
        if not isinstance(acquisition, Acquisition):
            raise Q1TypeError(f'Unsupported type for acquisition: {acquisition}')

        if acquisition.name not in self.acquisitions:
            self.acquisitions[acquisition.name] = {
                    'num_bins': acquisition.num_bins,
                    'index': len(self.acquisitions),
                    }

        return self.acquisitions[acquisition.name]['index']

    def translate_weight(self, weight):
        if not isinstance(weight, AcquisitionWeight):
            raise Q1TypeError(f'Unsupported type for weight: {weight}')

        if weight.name not in self.weights:
            index = len(self.weights)
            if index >= Q1Configuration.MAX_NUM_WEIGHTS - 1:
                raise Q1MemoryError("Too many acquisition weights")
            size_weights = self._size_weights + len(weight.data)
            if size_weights > Q1Configuration.WEIGHTS_MEM_SIZE:
                raise Q1MemoryError("Too much acquisition weight data for memory")
            self._size_weights = size_weights
            self.weights[weight.name] = {
                    'data': weight.data.tolist(),
                    'index': index,
                    }

        return self.weights[weight.name]['index']

    def get_data_dict(self):
        return {
                'waveforms': self.waveforms,
                'weights': self.weights,
                'acquisitions': self.acquisitions,
                }
