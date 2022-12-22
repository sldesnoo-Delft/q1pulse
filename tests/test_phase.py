
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])

p = instrument.new_program('phase')
p.repetitions = 100

P1 = p.P1

p.R.phase1 = 0.125
P1.Rs.phase2 = -0.125
p.wait(60)
P1.set_phase(0.5)

p.wait(348)
P1.set_phase(p.R.phase1)

p.wait(188)
P1.shift_phase(P1.Rs.phase2,hires_reg=False)

p.wait(348)
P1.shift_phase(P1.Rs.phase2 + 0.1)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

