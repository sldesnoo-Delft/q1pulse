from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])

p = instrument.new_program('asr')

seq = p.P1

p.R.a = 1
p.R.b = 2

p.R.c = p.R.a >> 2

p.R.d = p.R.a >> p.R.b

p.R.e = -9
p.R.f = p.R.e >> 1  # q1asm evaluation
p.R.h = -9 >> 1     # Python evaluation

seq.describe()

p.compile(annotate=True, listing=True, verbose=True)

instrument.run_program(p)

if hasattr(qcm0, 'print_registers'):
    # get result from Q1Simulator
    qcm0.print_registers(0, range(10))
