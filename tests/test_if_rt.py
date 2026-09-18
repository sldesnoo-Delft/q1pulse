import matplotlib.pyplot as plt
from pprint import pprint
from q1pulse.instrument import Q1Instrument
from q1pulse.lang.program_variables import IntVariable, FloatVariable

from init_pulsars import qcm0, q1asm_isa_v2

if not q1asm_isa_v2:
    raise Exception("'test_variables' cannot be executed for Q1ASM v1.0")

instrument = Q1Instrument('q1_v2' if q1asm_isa_v2 else 'q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])

p = instrument.new_program('if_rt')

P1 = p.P1

# just add some waiting time to prevent error messages on real-time executor
p.wait(100)
P1.set_offset(0.0)


p.R.a = IntVariable(init_scope='load', initial_value=10)  # Name is "a"
p.R.b = IntVariable(init_scope='load', initial_value=10)
p.R.c = IntVariable()
p.R.d = IntVariable()

p.R.d = 0
p.R.c = 1

with p.if_(p.R.a > p.R.b):
    p.R.c = 10

with p.if_(p.R.a == p.R.b):
    p.R.d = 2
    P1.wait(10)
    P1.block_pulse(100, 0.2)
with p.elif_(p.R.a < p.R.b):
    p.R.d = 3
    P1.wait(20)
    P1.block_pulse(10, 0.4)
with p.else_:
    p.R.d = 4
    P1.wait(10)
    P1.block_pulse(80, 0.6)

p.wait(10)

P1.describe()

p.compile(annotate=True, listing=True, optimize=0)

print(p.list_variables())

instrument.load_program(p)
instrument.start_program(p)
instrument.wait_stopped()

# if hasattr(qcm0, 'print_registers'):
#     # get result from Q1Simulator
#     qcm0.print_registers(0, range(20))

pprint(instrument.get_variables())
plt.figure()
qcm0.plot()


instrument.set_variables({
    "a": 0,
    })
instrument.start_program(p)
instrument.wait_stopped()
pprint(instrument.get_variables())
plt.figure()
qcm0.plot()


instrument.set_variables({
    "a": 20,
    })
instrument.start_program(p)
instrument.wait_stopped()
pprint(instrument.get_variables())
plt.figure()
qcm0.plot()
