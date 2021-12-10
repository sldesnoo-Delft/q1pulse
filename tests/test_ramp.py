
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0
from plot_util import plot_output

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])

p = instrument.new_program('ramp')
p.repetitions = 2

P1 = p.P1
P2 = p.P2


P1.block_pulse(40, -0.25)
P2.ramp(40, 0.0, 1.0)
P1.block_pulse(40, 0.5)
p.wait(20)
P1.ramp(320, 0.0, 0.8)
P1.ramp(200, 0.8, 0.4)
with p.parallel():
    P2.ramp(152, -0.5, -1.0)
    P1.ramp(100, -0.5, -1.0)
    P1.ramp(52, -1.0, -0.5, t_offset=100)
P2.ramp(40, -1.0, -0.2)


p.wait(100)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
