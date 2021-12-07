import numpy as np
import scipy.signal as signal

from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('P1', qcm0.name, [0])
instrument.add_control('P2', qrm1.name, [1])
instrument.add_readout('R1', qrm1.name, [])

qrm1.in0_gain(0)
qrm1.in1_gain(0)

p = instrument.new_program('acquire')
p.repetitions = 1

P1 = p.P1
P2 = p.P2
R1 = p.R1

N = 7
n_acq = N*N*p.repetitions
R1.add_acquisition_bins('non-weighed', n_acq)
R1.add_acquisition_bins('weighed', n_acq)
R1.add_weight('gaus100', signal.gaussian(100, 12))
R1.integration_length_acq = 100

amplitude = 0.125

# output range QCM (P1): +/- 2.5 V
# output range QRM (P1): +/- 0.5 V
# input range QRM (R1): +/- 0.5 V

v1_max = 0.5/2.5*0.9
v2_max = 0.5/0.5*0.9

with p.loop_linspace(-v1_max, v1_max, N) as v1:
    with p.loop_linspace(-v2_max, v2_max, N) as v2:
        with p.parallel():
            P1.block_pulse(500, v1)
            P2.block_pulse(500, v2)
            # delay from output to input is ~108 ns
            R1.acquire('non-weighed', 'increment', t_offset=112)

        with p.parallel():
            P1.block_pulse(500, v1)
            P2.block_pulse(500, v2)
            R1.acquire_weighed('weighed', 'increment', 'gaus100', t_offset=120)

        p.wait(1100)

#p.describe()
#print()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

# @@@ program should return data.
data_n = instrument.get_acquisition_bins('R1', 'non-weighed')
data_w = instrument.get_acquisition_bins('R1', 'weighed')

dn0 = np.array(data_n['integration']['path0']).reshape((p.repetitions,N,N))
dn1 = np.array(data_n['integration']['path1']).reshape((p.repetitions,N,N))
dw0 = np.array(data_w['integration']['path0']).reshape((p.repetitions,N,N))
dw1 = np.array(data_w['integration']['path1']).reshape((p.repetitions,N,N))

with np.printoptions(precision=2, threshold=1000):
    print('non-weighed')
    print(dn0)
    print(dn1)
    print('weighed')
    print(dw0)
    print(dw1)
