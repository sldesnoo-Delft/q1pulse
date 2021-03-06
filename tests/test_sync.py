from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1
from plot_util import plot_output

# Do not specify path. This is not a Q1ASM reference test.
instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('P1', qrm1.name, [0])
instrument.add_control('P2', qcm0.name, [1])
instrument.add_control('P3', qcm0.name, [2])
instrument.add_control('P4', qcm0.name, [3])
instrument.add_control('R1', qrm1.name, [1])

p = instrument.new_program('sync')
p.repetitions = 10_000_000

t = 5000
a = 1.0

P1 = p.P1
P2 = p.P2

gates=['P1', 'P2', 'P3', 'P4', 'R1']
with p.loop_range(1000):
    p.set_offsets(gates, [-a]*5)
    p.wait(t)
    p.set_offsets(gates, [a]*5)
    p.wait(t)

#p.set_offsets(gates, [0.0]*4)
#p.wait(t)
p.describe()

p.compile(listing=True)

instrument.run_program(p)

plot_output([qcm0, qrm1])
