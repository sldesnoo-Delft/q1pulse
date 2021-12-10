
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1
from plot_util import plot_output

instrument = Q1Instrument()
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])
instrument.add_readout('R1', qrm1.name, [1])

p = instrument.new_program('csd')
P1 = p.P1
P2 = p.P2
R1 = p['R1'] # using alternative notation

N = 100
R1.add_acquisition_bins('default', N*N)

gates=[P1, P2] # alternative notation: ['P1', 'P2']
t_measure = 2000
t_acqdelay = 500
t_step = t_measure + t_acqdelay

with p.loop_linspace(-0.5, 0.5, N) as v2:
    with p.loop_linspace(-0.5, 0.5, N) as v1:
        with p.parallel():
            p.wait(t_step)
            P2.set_offset(v2)
            P1.set_offset(v1)
            R1.acquire('default', 'increment', t_offset=t_acqdelay)

P1.set_offset(0.0)
P2.set_offset(0.0)

p.describe()

p.compile(annotate=True, listing=True)

instrument.run_program(p)

plot_output([qcm0, qrm1])
