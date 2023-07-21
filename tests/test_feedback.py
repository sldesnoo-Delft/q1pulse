import numpy as np

from q1pulse.instrument import Q1Instrument
from q1pulse.lang.conditions import Operators

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
instrument.add_readout('R1', qrm1.name, [])

# gain = 0: +/- 0.5V; gain -6 dB: +/- 1.0 V
vmax_in = 0.5
qrm1.in0_gain(0)
qrm1.in1_gain(0)

p = instrument.new_program('feedback')
p.repetitions = 2

trigger1 = p.configure_trigger('R1')
counter1 = p.add_trigger_counter(trigger1)

P1 = p.P1
R1 = p.R1

n_acq = p.repetitions
R1.add_acquisition_bins('measurements', n_acq)
R1.integration_length_acq = 100
R1.thresholded_acq_threshold = 0.1

# program
R1.acquire('measurements')
p.wait(20)
p.latch_reset()
p.wait(20)
P1.latch_enable([counter1])
p.wait(60)
P1.set_markers(0b1111)
P1.ramp(60, -0.5, -0.25)
p.wait(40)
P1.set_markers(0b0000)
P1.ramp(60, 0.25, 0.5)
p.wait(120)
with P1.conditional([counter1], evaluation_time=20) as flags:
    with flags.all_set():
        P1.ramp(60, 0.25, 0.25)
    with flags.none_set():
        P1.ramp(60, 0.25, 0.0)

p.wait(40)
with p.conditional([counter1]) as flags:
    with flags.all_set():
        P1.ramp(60, 0.25, 0.25)

p.wait(40)
P1.ramp(60, 0.25, 0.5)
p.wait(20)
P1.latch_enable([])
p.wait(20)

#p.describe()
#print()

p.compile(listing=True)#, annotate=True)

#%% Set Mock data

set_mock_data(qrm1, 0, 'measurements',
              np.array([0.2, -0.2]) * R1.integration_length_acq)

#%% Run and plot
# run and get results
instrument.run_program(p)

plot_output([qcm0, qrm1])

data = instrument.get_acquisition_bins('R1', 'measurements')

