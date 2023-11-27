
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0
from plot_util import plot_output

# %%
instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('q1', qcm0.name, [0, 1], nco_frequency=100e6)
# add Q on channel 2, I on channel 3
instrument.add_control('q2', qcm0.name, [3, 2], nco_frequency=50e6)

p = instrument.new_program('baseband')
p.repetitions = 1

q1 = p.q1
q2 = p.q2

q1.block_pulse(100, 0.5)
q2.block_pulse(100, 0.4)


p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
