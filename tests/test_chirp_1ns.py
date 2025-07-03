

from init_pulsars import qcm0
from plot_util import plot_output

# %%
from q1pulse.instrument import Q1Instrument
instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('q1', qcm0.name, [0, 1], nco_frequency=0)
instrument.add_control('P1', qcm0.name, [2], nco_frequency=0)

# %%

p = instrument.new_program('chirp_1ns')
p.repetitions = 1

q1 = p.q1
P1 = p.P1

P1.block_pulse(7, 0.2)
q1.chirp(1000, 0.5, 10e6, 40e6)

P1.block_pulse(7, 0.2)
q1.chirp(999, 0.5, 10e6, 40e6)

P1.block_pulse(7, 0.2)
q1.chirp(998, 0.5, 10e6, 40e6)

P1.block_pulse(7, 0.2)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
