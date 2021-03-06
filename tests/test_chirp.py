from q1pulse.instrument import Q1Instrument
from q1pulse.util.shapes import add_chirp

from init_pulsars import qcm0
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)

# use 4 max sequencers for chirp
for s in 'abcd':
    seq = instrument.add_control('q1'+s, qcm0.name, [2,3])

instrument.add_control('P1', qcm0.name, [1])

p = instrument.new_program('chirp')

P1 = p.P1
qs = []
for s in 'abcd':
    qs.append(p['q1'+s])

P1.block_pulse(100, 0.5)
p.wait(100)
add_chirp(10000, -10e6, 10e6, 0.5, qs)

p.describe()
print()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
