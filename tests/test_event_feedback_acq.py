import numpy as np

from q1pulse.instrument import Q1Instrument
from q1pulse.lang.program_variables import IntVariable, FloatVariable

from init_pulsars import qcm0, qrm1, q1asm_isa_v2

from plot_util import plot_output

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(filename='test_log.txt', encoding='utf-8', level=logging.DEBUG)


def set_mock_data(qrm, seq_nr, acq_name, data):
    seq = qrm.sequencers[seq_nr]
    if hasattr(seq, 'set_acquisition_mock_data'):
        seq.set_acquisition_mock_data([data], name=acq_name, repeat=True)


instrument = Q1Instrument('q1_v2' if q1asm_isa_v2 else 'q1')
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('P1', qcm0.name, [0])
instrument.add_readout('R1', qrm1.name, out_channels=[], in_channels=[0])

# qcm0.config('trace', True)

# gain = 0: +/- 0.5V; gain -6 dB: +/- 1.0 V
vmax_in = 0.5
qrm1.in0_gain(0)
qrm1.in1_gain(0)

p = instrument.new_program('event_feedback_acq')
p.repetitions = 2

P1 = p.P1
R1 = p.R1

n_acq = p.repetitions
R1.add_acquisition_bins('measurements', n_acq)
R1.integration_length_acq = 100
R1.thresholded_acq_threshold = 0.1

# program
event_tb = p.register_feedback_event("m1_tb")
event_iq = p.register_feedback_event("m1_iq")
P1.Rs.m1_tb = IntVariable()
P1.Rs.m1_i = FloatVariable()
P1.Rs.m1_q = FloatVariable()

p.wait(4)
R1.fb_acq_tb_id(event_tb, wait_after=4)
R1.fb_acq_iq_id(event_iq, wait_after=4)

p.P1.block_pulse(100, 0.2)
p.wait(50)
R1.acquire('measurements')
p.wait(650)
P1.fb_pop_data(event_tb, P1.Rs.m1_tb)
P1.fb_pop_data(event_iq, P1.Rs.m1_i)
P1.fb_pop_data(event_iq, P1.Rs.m1_q)
p.wait(20)

# p.describe()
# print()

p.compile(listing=True)

# %% Set Mock data

set_mock_data(qrm1, 0, 'measurements',
              np.array([0.2, -0.2]) * R1.integration_length_acq)

# %% Run and plot
# run and get results
instrument.run_program(p)
instrument.save_program(p, "test_q1")

print(instrument.get_variables())

plot_output([qcm0, qrm1])

data = instrument.get_acquisition_bins('R1', 'measurements')
