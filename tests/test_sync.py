from pprint import pprint
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_qrm(1, qrm1)
instrument.add_control('P1', 1, [0])
instrument.add_control('P2', 0, [1])
instrument.add_control('P3', 0, [2])
instrument.add_control('P4', 0, [3])

p = instrument.new_program('sync')
p.repetitions = 10_000_000

P1 = p.P1
P2 = p.P2

gates=['P1', 'P2', 'P3', 'P4']
with p.loop_range(2):
    p.set_offsets(gates, [-0.1, -0.1, -0.1, -0.1])
    p.wait(12)
    p.set_offsets(gates, [0.1, 0.1, 0.1, 0.1])
    p.wait(12)

p.set_offsets(gates, [0.0, 0.0, 0.0, 0.0])
p.wait(10000)
p.describe()

p.compile(listing=True)

instrument.run_program(p)
