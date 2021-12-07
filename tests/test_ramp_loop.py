
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])

p = instrument.new_program('ramp_loop')
p.repetitions = 2

P1 = p.P1
P2 = p.P2

p.R.v_ramp1 = 1.0

P1.block_pulse(40, -0.25)
P2.ramp(40, 0.0, p.R.v_ramp1)
P1.block_pulse(40, 0.5)
p.wait(20)

with p.loop_linspace(-0.5, 0.5, 5) as v_ramp:
    with p.parallel():
        P2.ramp(280, v_ramp, -0.4)
        P1.ramp(80, v_ramp, -0.4, t_offset=8)
        P1.ramp(180, -0.4, v_ramp, t_offset=88)
    P2.ramp(480, v_ramp, v_ramp + 0.2)


p.wait(100)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)
