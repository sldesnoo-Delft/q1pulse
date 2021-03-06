
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])

p = instrument.new_program('phase')
p.repetitions = 10

P1 = p.P1

p.R.phase1 = 0.125
P1.Rs.phase2 = -0.125

P1.set_phase(0.5)
p.wait(100)
P1.set_phase(p.R.phase1)
p.wait(100)
P1.shift_phase(P1.Rs.phase2)
p.wait(100)
P1.shift_phase(P1.Rs.phase2 + 0.1)
p.wait(200)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

