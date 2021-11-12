
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_qrm(1, qrm1)
instrument.add_control('q1', 0, [0,1])
instrument.add_control('P1', 0, [2])
instrument.add_control('P2', 0, [3])
instrument.add_readout('R1', 1, [1])

p = instrument.new_program('rabi')
p.repetitions = 1000

q1 = p.q1
P1 = p.P1
P2 = p.P2
R1 = p['R1']

gates=['P1', 'P2']
v_init = [0.120, 0.040]
v_manip = [0.0, 0.0]
v_read = [-0.030, 0.060]
rabi_amplitude = 0.13

with p.loop_range(100, 1000, 10) as t_pulse:
    #init
    p.block_pulse(200, gates, v_init)
    p.wait(20)

    # manip
    q1.block_pulse(t_pulse, rabi_amplitude)

    # read
    p.ramp(200, gates, v_manip, v_read)
    with p.parallel():
        p.set_offsets(gates, v_read)
        p.wait(1000)
        R1.acquire(0, "increment", t_offset=100)

p.describe()

p.compile(listing=True)

instrument.run_program(p)
