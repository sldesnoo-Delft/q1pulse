import matplotlib.pyplot as pt
import numpy as np

from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, q1asm_isa_v2
from plot_util import plot_output
# %%
instrument = Q1Instrument('q1_v2' if q1asm_isa_v2 else 'q1')
instrument.add_qcm(qcm0)
instrument.add_control('q1', qcm0.name, [0, 1], nco_frequency=0)
# %%
p = instrument.new_program('frequency_phase')
p.repetitions = 1

q1 = p.q1
q1.set_offset(1.0)
q1.set_frequency(10e6)
p.wait(100)
q1.shift_phase(0.5)
p.wait(100)

q1.set_offset(0.0)
q1.shift_phase(-0.5)
p.wait(100)
q1.set_phase(0.0)
q1.set_offset(1.0)
q1.set_offset(1.0)
q1.set_frequency(-10e6)
p.wait(100)
q1.shift_phase(0.5)
p.wait(100)
q1.set_offset(0.0)
p.wait(20)

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])

pt.ylim(-3, 3.5)
pt.grid()

# %%
t = np.arange(520)
renderer = qcm0.sequencer0.rt_renderer

out0 = np.concatenate(renderer.out0)
out1 = np.concatenate(renderer.out1)

phase = np.angle(out0+1j*out1)
pt.figure()
pt.plot(t, phase, label='phase')
pt.grid()
pt.legend()
