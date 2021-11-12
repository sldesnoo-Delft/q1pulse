import scipy.signal as signal

from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_control('q1', 0, [0,1])
instrument.add_control('P1', 0, [2])
instrument.add_control('P2', 0, [3])

p = instrument.new_program('shaped')
p.repetitions = 1000

q1 = p.q1
P1 = p.P1
P2 = p.P2

gauss80 = q1.add_wave('gauss80', signal.gaussian(80, std=0.12 * 80))

amplitude = 0.125

q1.shaped_pulse(gauss80, 0.5, gauss80, 0.5)
p.wait(50)
q1.shaped_pulse('gauss80', amplitude, 'gauss80', amplitude)

p.wait(50)
with p.parallel():
    P1.block_pulse(100, 0.25)
    P2.block_pulse(100, -0.25)
    q1.shaped_pulse(gauss80, amplitude)

p.describe()
print()

p.compile(verbose=True, listing=True, annotate=True)

instrument.run_program(p)
