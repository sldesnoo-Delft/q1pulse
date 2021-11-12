
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_qrm(1, qrm1)
instrument.add_control('P1', 0, [2])
instrument.add_control('P2', 0, [3])
instrument.add_readout('R1', 1, [1])

p = instrument.new_program('csd')
P1 = p.P1
P2 = p.P2
R1 = p['R1'] # using alternative notation

R1.add_acquisition_bins('default', 10)

gates=[P1, P2] # alternative notation: ['P1', 'P2']
v_init = [120, 40]
v_manip = [0, 0]
v_read = [-30, 60]
t_measure = 2000
t_acqdelay = 500
t_step = t_measure + t_acqdelay

# @@@ alternating loop:
# load start + end in regs
# inner loop 2 iterations, move end -> loop_var; decrement counter
with p.loop_linspace(0.0, 1.0, 2) as v2:
    P2.set_offset(v2)
    p.wait(4)
    with p.loop_linspace(-0.5, 0.5, 3) as v1:
        with p.parallel():
            p.wait(t_step)
            P1.set_offset(v1)
            R1.acquire('default', 'increment', t_offset=t_acqdelay)

P1.set_offset(0.0)
P2.set_offset(0.0)

p.describe()

p.compile(annotate=True, listing=True)

instrument.run_program(p)
