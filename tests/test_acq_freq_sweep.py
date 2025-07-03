import numpy as np
import matplotlib.pyplot as pt

from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('q1', qcm0.name, [0, 1], nco_frequency=200e6)
instrument.add_readout('rf1', qrm1.name, [0, 1], nco_frequency=0e6)

qrm1.in0_gain(0)
qrm1.in1_gain(0)
# %%
amplitude = 0.5
N = 101
period = 1000
f_start = -250e6
f_stop = 250e6

p = instrument.new_program('acq_rf_sweep')
p.repetitions = 1

q1 = p.q1
rf1 = p.rf1

rf1.add_acquisition_bins("default", N)
rf1.integration_length_acq = 1000
rf1.nco_prop_delay = 148  # ~ 50 cm line

q1.set_offset(amplitude, 0.0)
rf1.set_offset(amplitude)
rf1.acquire_frequency_sweep(N, period,
                            f_start, f_stop,
                            "default",
                            acq_delay=152)
rf1.wait(period)

rf1.set_offset(0.0)
q1.set_offset(0.0)

p.compile(listing=True)

# %%
instrument.run_program(p)


data = instrument.get_acquisition_bins('rf1', 'default')

# pprint(data)
I = np.array(data['integration']['path0'])/rf1.integration_length_acq
Q = np.array(data['integration']['path1'])/rf1.integration_length_acq
c = I + 1j*Q
# for i in range(N):
#     print(f'{I[i]:6.3f}, {Q[i]:6.3f}, {abs(c[i]):6.3f}, {np.angle(c[i])/np.pi:5.3f}')

pt.close('all')
pt.figure()
pt.plot(np.angle(c)/np.pi)
pt.title('phase')

pt.figure()
pt.plot(np.abs(c))
pt.title('amplitude')
pt.ylim(0, 0.6)

np.abs(c)
