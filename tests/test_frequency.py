
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])

p = instrument.new_program('frequency')
p.repetitions = 2

P1 = p.P1
P1.nco_frequency = 1e6

p.R.frequency = int(12e6)
P1.Rs.frequency = int(30e6)

P1.set_offset(0.5)
P1.set_frequency(10e6)
p.wait(100)
P1.set_frequency(5e6)
p.wait(100)
P1.set_frequency(p.R.frequency)
p.wait(100)
P1.set_frequency(P1.Rs.frequency)
p.wait(100)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
