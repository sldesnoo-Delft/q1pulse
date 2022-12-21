import time

from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])
instrument.add_readout('R1', qrm1.name, [1])

p = instrument.new_program('csd_ramp')
P1 = p.P1
P2 = p.P2
R1 = p['R1'] # using alternative notation

N = 100
R1.add_acquisition_bins('default', N*N)

gates=[P1, P2] # alternative notation: ['P1', 'P2']
t_measure = 10_000
t_acqdelay = 500
t_step = t_measure + t_acqdelay

with p.loop_linspace(-0.5, 0.5, N) as v2:
    with p.parallel():
        P2.block_pulse(t_step*N, v2)
        P1.ramp(t_step*N, -0.5, 0.5)
        R1.repeated_acquire(N, t_step,
                            'default', 'increment',
                            t_offset=t_acqdelay)

#p.describe()

p.compile(annotate=True, listing=True)

#%%
start = time.perf_counter()
instrument.run_program(p)
duration = time.perf_counter() - start
print(f'{duration*1000:6.3f} ms')
#%%
plot_output([qcm0, qrm1])
