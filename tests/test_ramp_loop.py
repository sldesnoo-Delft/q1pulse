
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])

p = instrument.new_program('ramp_loop')
p.repetitions = 2

P1 = p.P1
P2 = p.P2

p.R.v_ramp1 = 0.2

P1.block_pulse(100, -0.1)
P1.block_pulse(40, 0.5)
p.wait(20)
P2.ramp(40, 0.0, p.R.v_ramp1)
P2.ramp(40, 0.2, p.R.v_ramp1)
P2.ramp(40, 0.2, 0.0)

with p.loop_linspace(-0.5, 0.5, 5) as v_ramp:
    with p.parallel():
        P2.ramp(480, 0.0, v_ramp+0.05)
        P2.ramp(140, v_ramp+0.05, 0.0, t_offset=480)
        P1.ramp(360, 0.0, v_ramp, t_offset=120)
        P1.ramp(80, v_ramp, 0.0, t_offset=480)

p.wait(100)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
