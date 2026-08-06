from pprint import pprint
from q1pulse.instrument import Q1Instrument
from q1pulse.lang.program_variables import IntVariable, FloatVariable

from init_pulsars import qcm0

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])

p = instrument.new_program('variables')

seq = p.P1

# just add some waiting time to prevent error messages on real-time executor
p.wait(1000)
p.P1.set_offset(0.0)


p.R.a = IntVariable(init_scope='load', initial_value=10)  # Name is "a"
p.R.b = IntVariable()
p.R.c = IntVariable()

p.R.b = p.R.a + 1
p.R.b = 5 + p.R.a + 1
p.R.c = p.R.a * p.R.b

# floating point
p.R.x = FloatVariable(init_scope="load", initial_value=1.0)
p.R.x -= 0.8

p.R.y = FloatVariable()
p.R.y = 0.5
p.R.z = p.R.x - p.R.y

# sequencer registers
seq.Rs.p1 = 9
seq.Rs.q1 = seq.Rs.p1 + p.R.b
seq.Rs.v1 = IntVariable(init_scope="load", initial_value=0)
seq.Rs.v1 = seq.Rs.q1 + p.R.a

seq.Rs.v2 = FloatVariable()
seq.Rs.v2 = p.R.x * p.R.y

# bitwise
seq.Rs.a1 = 0b0011
seq.Rs.b1 = seq.Rs.a1 & 0b0101
seq.Rs.c1 = seq.Rs.a1 | 0b0101
seq.Rs.d1 = 0b0101 ^ seq.Rs.a1
seq.Rs.e1 = ~seq.Rs.a1

seq.describe()

p.compile(annotate=True, listing=True, optimize=0)

print(p.list_variables())

instrument.load_program(p)
instrument.start_program(p)
instrument.wait_stopped()

if hasattr(qcm0, 'print_registers'):
    # get result from Q1Simulator
    qcm0.print_registers(0, range(20))

pprint(instrument.get_variables())

instrument.set_variables({
    "a": -2,
    "x": 0.0,
    })
instrument.start_program(p)
instrument.wait_stopped()
pprint(instrument.get_variables())
