import scipy.signal as signal

from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_qrm(1, qrm1)
instrument.add_control('P1', 0, [2])
instrument.add_control('P2', 0, [3])
instrument.add_readout('R1', 1, [0,1])

p = instrument.new_program('acquire')
p.repetitions = 1000

P1 = p.P1
P2 = p.P2
R1 = p.R1

R1.add_acquisition_bins('default', 10)
R1.add_weight('gaus100', signal.gaussian(100, 12))

amplitude = 0.125

with p.parallel():
    P1.block_pulse(100, 0.25)
    P2.block_pulse(100, -0.25)
    R1.acquire('default', 'increment')

with p.parallel():
    P1.block_pulse(100, 0.25)
    P2.block_pulse(100, -0.25)
#    R1.acquire_weighed('default', 'increment', 'gaus100')
    R1.acquire_weighed('default', 0, 'gaus100') # @@@

p.describe()
print()

p.compile(verbose=True, listing=True, annotate=True)

instrument.run_program(p)
