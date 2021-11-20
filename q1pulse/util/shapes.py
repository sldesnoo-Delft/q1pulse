import math
import numpy as np

def add_chirp(duration, f_start, f_stop, amplitude,
              sequencers, max_samples=8192):
    n_slices = math.ceil(duration / max_samples)
    if n_slices > len(sequencers):
        raise Exception(f'Not enough sequencers. At least {n_slices} '
                        f'sequencers are needed for chirp of {duration} ns')

    f_step = (f_stop - f_start)/(duration * 1e-9)
    for i in range(n_slices):
        seq = sequencers[i]
        n_samples = min(duration - i*max_samples, max_samples)
        t = (np.arange(n_samples) + i*max_samples) * 1e-9
        phase = 2*np.pi * (f_step * 0.5 * t**2 + f_start*t)
        wave0 = seq.add_wave(f'chirp_I{i}', np.sin(phase))
        wave1 = seq.add_wave(f'chirp_Q{i}', np.cos(phase))
        seq.shaped_pulse(wave0, amplitude, wave1)
