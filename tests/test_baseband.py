
from q1pulse.instrument import QbInstrument

instrument = QbInstrument(dummy=True)
instrument.add_qcm(0, '192.168.0.2')
instrument.add_qrm(1, '192.168.0.3')
instrument.add_control('P1', 0, [2])
instrument.add_control('P2', 0, [3])

p = instrument.new_program('baseband')
p.repetitions = 1000

P1 = p.P1
P2 = p.P2

p.R.amplitude = 0.125
P1.Rs.amplitude = -0.125

P1.block_pulse(20, p.R.amplitude)
P1.block_pulse(200, P1.Rs.amplitude)
P1.block_pulse(20, p.R.amplitude + 0.5)
p.wait(50)
P1.block_pulse(100, 0.5)
P2.block_pulse(100, -0.5)

p.wait(50)
with p.parallel():
    P1.block_pulse(100, 0.25)
    P2.block_pulse(100, -0.25)

p.add_comment('--- long wait')
p.wait(100_000)
P1.block_pulse(10, -1.0)
p.add_comment('--- longer wait')
p.wait(160_000)
P1.block_pulse(10, 0.5)
p.add_comment('--- very long wait')
p.wait(500_000)
P1.block_pulse(10, 0.75)
P2.block_pulse(10, -0.75)

p.describe()
print()

p.compile(verbose=True, listing=True, annotate=True)

instrument.connect()
instrument.run_program(p)
#
#exe.list_program()