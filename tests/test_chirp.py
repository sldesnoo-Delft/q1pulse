
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('q1', qcm0.name, [0,1], nco_frequency=0)

p = instrument.new_program('chirp')
p.repetitions = 1

q1 = p.q1

q1.chirp(20_000, 0.5, -10e6, 10e6)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
