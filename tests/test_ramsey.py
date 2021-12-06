
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_qrm(1, qrm1)
instrument.add_control('q1', 0, [0,1])
instrument.add_control('P1', 0, [2])
instrument.add_control('P2', 0, [3])
instrument.add_readout('R1', 1, [1])

p = instrument.new_program('ramsey')
p.repetitions = 1000

q1 = p.q1
P1 = p.P1
P2 = p.P2
R1 = p['R1']

R1.add_acquisition_bins('default', 10)

gates=['P1', 'P2']
v_init = [0.120, 0.040]
v_manip = [0.0, 0.0]
v_read = [-0.030, 0.060]
t_pulse = 80
v_pulse = 0.8

with p.loop_range(200, 2000, 10) as t_wait:
    p.block_pulse(200, gates, v_init)
    p.ramp(20, gates, v_init, v_manip)

    q1.block_pulse(t_pulse, v_pulse)
    p.wait(t_wait)
    q1.block_pulse(t_pulse, v_pulse)

    p.ramp(100, gates, v_manip, v_read)
    with p.parallel():
        p.set_offsets(gates, v_read)
        p.wait(1000)
        R1.acquire('default', 'increment', t_offset=100)
    p.set_offsets(gates, [0.0, 0.0])

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)
