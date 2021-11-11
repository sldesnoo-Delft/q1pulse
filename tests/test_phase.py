
from q1pulse.instrument import QbInstrument

instrument = QbInstrument(dummy=True)
instrument.add_qcm(0, '192.168.0.2')
instrument.add_qrm(1, '192.168.0.3')
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

p.describe()
print()

p.compile(verbose=True, listing=True, annotate=True)

#instrument.connect()
#instrument.run_program(p)
#
#exe.list_program()