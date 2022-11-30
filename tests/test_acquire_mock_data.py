import numpy as np
import scipy.signal as signal

from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1
from plot_util import plot_output

def set_mock_data(qrm, seq_nr, acq_name, data):
    seq = qrm.sequencers[seq_nr]
    if hasattr(seq, 'set_acquisition_mock_data'):
        seq.set_acquisition_mock_data([data], name=acq_name, repeat=True)

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('P1', qcm0.name, [0])
instrument.add_control('P2', qrm1.name, [1])
instrument.add_control('P2c', qcm0.name, [1])
instrument.add_readout('R1', qrm1.name, [])

# gain = 0: +/- 0.5V; gain -6 dB: +/- 1.0 V
vmax_in = 0.5
qrm1.in0_gain(0)
qrm1.in1_gain(0)

p = instrument.new_program('acquire_mocked')
p.repetitions = 1

P1 = p.P1
P2 = p.P2
P2c = p.P2c
R1 = p.R1

N = 5
n_acq = N*N*p.repetitions
R1.add_acquisition_bins('non-weighed', n_acq)
R1.add_acquisition_bins('weighed', n_acq)
R1.add_weight('gaus100', signal.gaussian(100, 12))
#R1.add_weight('gaus100', np.ones(100))
R1.integration_length_acq = 100


# output range QCM (P1): +/- 2.5 V
# output range QRM (P1): +/- 0.5 V
# input range QRM (R1): +/- 0.5 V (gain = 0 dB)

v1_max = 0.4/2.5
v2_max = 0.4/0.5

with p.loop_linspace(-v1_max, v1_max, N) as v1:
    with p.loop_linspace(-v2_max, v2_max, N) as v2:
        with p.parallel():
            P1.block_pulse(500, v1)
            P2.block_pulse(500, v2)
            P2c.block_pulse(500, v1)
            # delay from output to input is ~108 ns
            R1.acquire('non-weighed', 'increment', t_offset=160)

        with p.parallel():
            P1.block_pulse(500, v1)
            P2c.block_pulse(500, v1)
            P2.block_pulse(500, v2)
            R1.acquire_weighed('weighed', 'increment', 'gaus100', t_offset=160)

        p.wait(1100)

#p.describe()
#print()

p.compile(listing=True, annotate=True)

#%% Set Mock data
data0 = np.linspace(-v1_max, v1_max, N).repeat(N)
data1 = np.tile(np.linspace(-v2_max, v2_max, N), N)

data0 = np.tile(data0, p.repetitions)
data1 = np.tile(data1, p.repetitions)

set_mock_data(qrm1, 1, 'non-weighed',
              np.array([data0, data1]).T * R1.integration_length_acq)
set_mock_data(qrm1, 1, 'weighed', (data0 + 1j*data1)/2)

#%% Run and plot
# run and get results
instrument.run_program(p)

plot_output([qcm0, qrm1])

# @@@ program should return data.
data_n = instrument.get_acquisition_bins('R1', 'non-weighed')
data_w = instrument.get_acquisition_bins('R1', 'weighed')

dn0 = np.array(data_n['integration']['path0']).reshape((p.repetitions,N,N))/R1.integration_length_acq*vmax_in
dn1 = np.array(data_n['integration']['path1']).reshape((p.repetitions,N,N))/R1.integration_length_acq*vmax_in
dw0 = np.array(data_w['integration']['path0']).reshape((p.repetitions,N,N))*vmax_in
dw1 = np.array(data_w['integration']['path1']).reshape((p.repetitions,N,N))*vmax_in

with np.printoptions(precision=2, threshold=1000):
    print('non-weighed')
    print(dn0)
    print(dn1)
    print('weighed')
    print(dw0)
    print(dw1)
