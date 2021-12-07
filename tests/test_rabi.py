import numpy as np
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('q1', qcm0.name, [0,1], nco_frequency=200e6)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])
instrument.add_readout('R1', qrm1.name, [], nco_frequency=200e6)
instrument.add_control('Ro1', qrm1.name, [0,1], nco_frequency=200e6)

qrm1.in0_gain(0)
qrm1.in1_gain(0)

p = instrument.new_program('rabi')
p.repetitions = 1

q1 = p.q1
P1 = p.P1
P2 = p.P2
R1 = p['R1']
Ro1 = p['Ro1']

R1.add_acquisition_bins('default', 20)
R1.integration_length_acq = 400

gates=['P1', 'P2']
v_init = [0.220, 0.040]
v_manip = [0.0, 0.0]
v_read = [-0.050, 0.060]
rabi_amplitude = 0.1
readout_amplitude = 0.1

p.R.bin=0
with p.loop_range(100, 2001, 100) as t_pulse:
    #init
    p.block_pulse(200, gates, v_init)
    p.wait(20)

    # manip
    q1.block_pulse(t_pulse, rabi_amplitude)

    # read
    p.ramp(200, gates, v_manip, v_read)
    with p.parallel():
        p.set_offsets(gates, v_read)
        Ro1.block_pulse(600, readout_amplitude)
#        R1.acquire('default', 'increment', t_offset=100)
        R1.acquire('default', p.R.bin, t_offset=100)
        p.wait(1000)
        p.R.bin += 1
    p.wait(1000)

#p.describe()

p.compile(listing=True)


instrument.run_program(p)

data = instrument.get_acquisition_bins('R1', 'default')

I = data['integration']['path0']
Q = data['integration']['path1']
for i in range(20):
    c = I[i] + 1j*Q[i]
    print(f'{I[i]:6.3f}, {Q[i]:6.3f}, {abs(c):6.3f}, {np.angle(c)/np.pi:5.3f}')