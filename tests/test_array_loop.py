
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_control('P1', 0, [2])
instrument.add_control('P2', 0, [3])

p = instrument.new_program('array_loop')
p.repetitions = 2

P1 = p.P1
P2 = p.P2

P1.block_pulse(40, -0.25)
P1.block_pulse(40, 0.5)
p.wait(20)

with p.loop_array([12,24,48,56,64]) as t_wait:
    P2.block_pulse(40, 0.5)
    p.wait(t_wait)
    P1.block_pulse(40, 0.25)
    p.wait(4)

p.wait(100)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)
