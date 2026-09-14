
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, q1asm_isa_v2
from plot_util import plot_output

# %%
instrument = Q1Instrument('q1_v2' if q1asm_isa_v2 else 'q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [0], nco_frequency=50e6, real_mode=True)

p = instrument.new_program('real_mode')
p.repetitions = 1

P1 = p.P1

P1.ramp_2paths(40, v_start0=0.0, v_end0=0.0, v_start1=0.0, v_end1=0.25)
P1.block_pulse(200, 0.1, 0.25)
P1.ramp_2paths(40, v_start0=0.0, v_end0=0.0, v_start1=0.25, v_end1=0.0)

P1.ramp_2paths(800, v_start0=0.0, v_end0=0.0, v_start1=0.0, v_end1=0.25)
P1.block_pulse(200, 0.1, 0.25)
P1.ramp_2paths(820, v_start0=0.0, v_end0=0.0, v_start1=0.25, v_end1=0.0)


p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])
