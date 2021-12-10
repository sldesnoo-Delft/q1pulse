
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0
from plot_util import plot_output

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])

p = instrument.new_program('baseband')
p.repetitions = 3

P1 = p.P1
P2 = p.P2

p.R.amplitude = 0.125
P1.Rs.amplitude = -0.125

P1.block_pulse(200, p.R.amplitude)
P1.block_pulse(200, P1.Rs.amplitude)
P1.block_pulse(200, p.R.amplitude + 0.5)
p.wait(1000)
P1.block_pulse(100, 0.5)
P2.block_pulse(100, -0.5)

p.wait(1000)
with p.parallel():
    P1.block_pulse(100, 0.25)
    P2.block_pulse(100, -0.25)

p.add_comment('--- long wait')
p.wait(100_000)
P1.block_pulse(500, -1.0)
p.add_comment('--- longer wait')
p.wait(160_000)
P1.block_pulse(500, 0.5)
p.add_comment('--- very long wait')
p.wait(500_000)
P1.block_pulse(1000, 0.75)
P2.block_pulse(1000, -0.75)
#
#p.describe()
#print()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
