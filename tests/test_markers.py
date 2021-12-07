
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qrm1.name, [0])

p = instrument.new_program('markers')
p.repetitions = 1000

P1 = p.P1
P2 = p.P2

with p.parallel():
    P1.block_pulse(20, -0.5)
    P2.block_pulse(20, -0.5)
p.wait(8)
with p.parallel():
    P1.set_markers(0b0001)
    P2.set_markers(0b0001)
    P1.block_pulse(20, 0.5)
    P2.block_pulse(20, 0.5)
P1.set_markers(0b0000)
P2.set_markers(0b0000)
p.wait(50_000)

p.describe()
print()

p.compile(verbose=True, listing=True, annotate=True)

instrument.run_program(p)
