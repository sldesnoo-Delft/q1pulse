
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])

p = instrument.new_program('loop_range')
p.repetitions = 3

P1 = p.P1
P2 = p.P2

with p.loop_range(20, 100, 20) as t_wait:
    P1.block_pulse(20, -0.1)
    P1.block_pulse(20, 0.8)
    p.wait(t_wait)
    P2.block_pulse(20, 0.6)
    p.wait(100)

# 4 pulses
with p.loop_range(-2, 2, 1) as t_wait:
    P1.block_pulse(20, 0.2)
    p.wait(20)

# 4 pulses
with p.loop_range(80, 0, -20) as t_wait:
    P1.block_pulse(20, 0.1)
    p.wait(t_wait + 10)

#p.describe()
#print()

p.compile(verbose=True, listing=True, annotate=True)

instrument.run_program(p)
