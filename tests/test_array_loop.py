
from q1pulse import Q1Instrument

from init_pulsars import qcm0
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])

p = instrument.new_program('array_loop')
p.repetitions = 2

P1 = p.P1
P2 = p.P2

P1.block_pulse(100, -0.1)
P1.block_pulse(40, 0.5)

p.wait(100)
with p.loop_array([0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 0.7]) as v:
    P2.log('amplitude', v, time=True)
    P2.block_pulse(80, v)

p.wait(100)
with p.loop_array([12,80,48,56,64]) as t_wait:
    P2.set_offset(0.5)
    P1.log('t_wait', t_wait, time=True)
    p.wait(t_wait)
    P1.log('after', None, time=True)
    P1.block_pulse(20, 0.25)
    p.wait(100 - t_wait)
    P2.set_offset(0.0)
    p.wait(100)

p.wait(100)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
