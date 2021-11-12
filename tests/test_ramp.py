
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_control('P1', 0, [2])
instrument.add_control('P2', 0, [3])

p = instrument.new_program('ramp')
p.repetitions = 1000

P1 = p.P1
P2 = p.P2


P2.ramp(50, 0.0, 1.0)
P1.block_pulse(100, -0.25)
#p.wait(50)
P1.ramp(300, 0.0, 0.125)
P1.ramp(200, 0.125, 0.5)
P2.ramp(250, -0.5, -1.0)


p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)
