
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_control('P1', 0, [2])

p = instrument.new_program('markers')
p.repetitions = 1000

P1 = p.P1


P1.set_markers(0b1000)
P1.block_pulse(20, 0.1)
p.wait(50)
P1.set_markers(0b0001)

p.describe()
print()

p.compile(verbose=True, listing=True, annotate=True)

instrument.run_program(p)
