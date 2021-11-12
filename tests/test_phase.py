
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_control('P1', 0, [2])

p = instrument.new_program('phase')
p.repetitions = 1000

P1 = p.P1

p.R.phase1 = 0.125
P1.Rs.phase2 = -0.125

P1.set_phase(0.5)
p.wait(50)
P1.set_phase(p.R.phase1)
p.wait(50)
P1.shift_phase(P1.Rs.phase2)
p.wait(50)
P1.shift_phase(P1.Rs.phase2 + 0.1)

p.describe()
print()

p.compile(verbose=True, listing=True, annotate=True)

instrument.run_program(p)
