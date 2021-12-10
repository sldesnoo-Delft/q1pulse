import numpy as np
import matplotlib.pyplot as pt
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1
from plot_util import plot_output

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('P1', qcm0.name, [0])
instrument.add_control('q1', qrm1.name, [0,1], nco_frequency=200e6)
instrument.add_readout('R1', qrm1.name, [], nco_frequency=200e6)

qrm1.in0_gain(0)
qrm1.in1_gain(0)

p = instrument.new_program('phase_shifting')
p.repetitions = 1

q1 = p.q1
R1 = p.R1

N = 1000

R1.add_acquisition_bins('default', N)
R1.integration_length_acq = 500

rabi_amplitude = 0.1
q1.Rs.phase_shift = 0.001
p.R.bin=0
with p.loop_range(N):

    with p.parallel():
        q1.block_pulse(600, rabi_amplitude)
        R1.acquire('default', p.R.bin, t_offset=120)
        p.R.bin += 1
    # for small phase shifts in register use hires_reg=True
    q1.shift_phase(q1.Rs.phase_shift, hires_reg=True)
    p.wait(500)
#    q1.Rs.phase_shift += 0.001

p.compile(listing=True)

instrument.run_program(p)

plot_output([qcm0, qrm1])

data = instrument.get_acquisition_bins('R1', 'default')

#pprint(data)
I = np.array(data['integration']['path0'])
Q = np.array(data['integration']['path1'])
c = I + 1j*Q
#for i in range(N):
#    print(f'{I[i]:6.3f}, {Q[i]:6.3f}, {abs(c[i]):6.3f}, {np.angle(c[i])/np.pi:5.3f}')

pt.figure()
pt.plot(np.angle(c)/np.pi)
pt.title('phase')

pt.figure()
pt.plot(np.abs(c))
pt.title('amplitude')
