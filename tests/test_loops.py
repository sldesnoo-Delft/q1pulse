
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_control('P1', 0, [2])
instrument.add_control('P2', 0, [3])

p = instrument.new_program('baseband')
p.repetitions = 3

P1 = p.P1
P2 = p.P2

with p.loop_linspace(0.2, 1.0, 5) as amplitude:
    P1.block_pulse(20, amplitude)
    P2.block_pulse(100, amplitude + 0.1)


#p.describe()
#print()

p.compile(verbose=True, listing=True, annotate=True)

instrument.run_program(p)
