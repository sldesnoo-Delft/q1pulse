from pprint import pprint
from q1pulse.instrument import Q1Instrument
from q1pulse.lang.program_variables import IntVariable, FloatVariable

from init_pulsars import qcm0, q1asm_isa_v2

if not q1asm_isa_v2:
    raise Exception("'test_variables' cannot be executed for Q1ASM v1.0")

instrument = Q1Instrument('q1_v2' if q1asm_isa_v2 else 'q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])

p = instrument.new_program('bool_evaluation')

seq = p.P1

# just add some waiting time to prevent error messages on real-time executor
p.wait(1000)
p.P1.set_offset(0.0)


p.R.a = IntVariable(init_scope='load', initial_value=10)  # Name is "a"
p.R.b = IntVariable(init_scope='load', initial_value=20)
p.R.c = IntVariable()
p.R.d = IntVariable()

p.R.d = 0
p.R.c = 1

p.R.c = (p.R.a > p.R.b)

p.R.d = (p.R.a > p.R.b) & (p.R.a > p.R.c)


seq.describe()

p.compile(annotate=True, listing=True, optimize=0)

print(p.list_variables())

instrument.load_program(p)
instrument.start_program(p)
instrument.wait_stopped()

# if hasattr(qcm0, 'print_registers'):
#     # get result from Q1Simulator
#     qcm0.print_registers(0, range(20))

pprint(instrument.get_variables())

instrument.set_variables({
    "a": -2,
    })
instrument.start_program(p)
instrument.wait_stopped()
pprint(instrument.get_variables())
