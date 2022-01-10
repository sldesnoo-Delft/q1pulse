from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('P1', qrm1.name, [0])
instrument.add_control('P2', qcm0.name, [1])
instrument.add_control('P3', qcm0.name, [2])
instrument.add_control('P4', qcm0.name, [3])

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

plot_output([qcm0, qrm1])
