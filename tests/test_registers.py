from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])

p = instrument.new_program('registers')

seq = p.P1

# just add some waiting time to prevent error messages on real-time executor
p.wait(1000)
p.P1.set_offset(0.0)


p.R.a = 10

p.R.b = p.R.a + 1
p.R.b = 5 + p.R.a + 1

p.R.c = p.R.b + p.R.a
p.R.c += 5
p.R.c -= 17
p.R.d = 1 - p.R.a

p.R.e = p.R.a << 2
p.R.f = p.R.a >> 2
p.R.h = p.R.d >> 2


# floating point
p.R.x = 1.0
p.R.x -= 0.8
p.R.y = 0.5
p.R.z = p.R.x - p.R.y

seq.Rs.x = 9
seq.Rs.y = seq.Rs.x + p.R.b

# bitwise
seq.Rs.a = 0b0011
seq.Rs.b = seq.Rs.a & 0b0101
seq.Rs.c = seq.Rs.a | 0b0101
seq.Rs.d = 0b0101 ^ seq.Rs.a
seq.Rs.e = ~seq.Rs.a

seq.describe()

p.compile(annotate=True, listing=True, verbose=True)

instrument.run_program(p)

if hasattr(qcm0, 'print_registers'):
    # get result from Q1Simulator
    qcm0.print_registers(0, range(20))

