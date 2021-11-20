from q1pulse.instrument import Q1Instrument
from q1pulse.util.shapes import add_chirp

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)

# use 4 max sequencers for chirp
for s in 'abcd':
    seq = instrument.add_control('q1'+s, 0, [0,1])

instrument.add_control('P1', 0, [2])

p = instrument.new_program('chirp')

P1 = p.P1
qs = []
for s in 'abcd':
    qs.append(p['q1'+s])

P1.block_pulse(100, 0.5)
add_chirp(30000, -40e6, 40e6, 0.1, qs)

p.describe()
print()

p.compile(verbose=True, listing=True, annotate=True)

instrument.run_program(p)
