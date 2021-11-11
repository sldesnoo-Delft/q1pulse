from q1pulse.instrument import QbInstrument

instrument = QbInstrument()
instrument.add_qcm(0, '192.168.0.2')
instrument.add_control('P1', 0, [2])

p = instrument.new_program('registers')

seq = p.P1

p.R.a = 0

p.R.b = p.R.a + 1
p.R.b = 5 + p.R.a + 1

p.R.c = p.R.b + p.R.a
p.R.c += 5
p.R.c -= 15

p.R.d = p.R.a << 2
p.R.d = p.R.a >> 2
p.R.e = 1 - p.R.a

p.R.f = 1.0
p.R.f -= 0.1
p.R.g = 0.5
p.R.h = p.R.f - p.R.g

seq.Rs.x = 9
seq.Rs.y = seq.Rs.x + p.R.b

p.R._registers

seq.describe()

p.compile(annotate=True, listing=True)

