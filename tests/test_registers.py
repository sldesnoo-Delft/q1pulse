from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])

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

# floating point
p.R.f = 1.0
p.R.f -= 0.1
p.R.g = 0.5
p.R.h = p.R.f - p.R.g

seq.Rs.x = 9
seq.Rs.y = seq.Rs.x + p.R.b

# bitwise
seq.Rs.a = 0b0011
seq.Rs.b = seq.Rs.a & 0b0101
seq.Rs.c = seq.Rs.a | 0b0101
seq.Rs.d = 0b0101 ^ seq.Rs.a
seq.Rs.e = ~seq.Rs.a

seq.describe()

p.compile(annotate=True, listing=True)

instrument.run_program(p)
