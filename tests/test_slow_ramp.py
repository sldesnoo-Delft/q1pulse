
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [0])
instrument.add_control('P2', qcm0.name, [1])
instrument.add_control('P3', qcm0.name, [2])

# %%

p = instrument.new_program('ramp_slow')
p.repetitions = 2

P1 = p.P1
P2 = p.P2
P3 = p.P3

c = 1

with p.parallel():
    # ramp just below stepping limit
    P1.ramp(6580, -0.001*c, 0.001*c)
    # ramp just above stepping limit
    P2.ramp(6580, -0.00101*c, 0.00101*c)
    P3.ramp(6580, -0.0011*c, 0.0011*c)

p.wait(100)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
