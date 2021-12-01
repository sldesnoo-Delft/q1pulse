from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_control('P1', 0, [2])

p = instrument.new_program('asr')

seq = p.P1

p.R.a = 1
p.R.b = 2

p.R.c = p.R.a >> 2

p.R.d = p.R.a >> p.R.b

seq.describe()

p.compile(annotate=True, listing=True)

instrument.run_program(p)
