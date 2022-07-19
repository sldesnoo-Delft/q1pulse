import init_logger
from q1pulse.instrument import Q1Instrument
import numpy as np

from init_pulsars import qcm0, qrm1
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('q1', qcm0.name, [0,1], nco_frequency=100e6)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])
instrument.add_readout('R1', qrm1.name, [])

p = instrument.new_program('shaped_block')
p.repetitions = 2

q1 = p.q1
P1 = p.P1
P2 = p.P2
R1 = p.R1


block80 = q1.add_wave('block80', np.ones(80))
block80 = P1.add_wave('block80', np.ones(80))

R1.add_acquisition_bins('acq_bins', p.repetitions)
R1.integration_length_acq = 80

amplitude = 0.125
p.R.wait = 20

with p.loop_range(4):
    q1.shaped_pulse(block80, 0.5, block80, 0.5)
    P1.shaped_pulse(block80, 0.1)
    p.wait(20)
    p.wait(p.R.wait)

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0, qrm1])

if hasattr(qrm1, 'print_acquisitions'):
    # get acquisition timing and counts from Q1Simulator
    qrm1.print_acquisitions()
