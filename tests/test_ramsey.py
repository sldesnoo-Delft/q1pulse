
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_qrm(qrm1)
instrument.add_control('q1', qcm0.name, [0,1], nco_frequency=50e6)
instrument.add_control('P1', qcm0.name, [2])
instrument.add_control('P2', qcm0.name, [3])
instrument.add_readout('R1', qrm1.name, [1])

p = instrument.new_program('ramsey')
p.repetitions = 2

q1 = p.q1
P1 = p.P1
P2 = p.P2
R1 = p['R1']

R1.add_acquisition_bins('q1value', 20)

gates=['P1', 'P2']
v_init = [0.120, 0.040]
v_manip = [0.0, 0.0]
v_read = [-0.030, 0.060]
t_pulse = 80
v_pulse = 0.5

R1.reset_bin_counter('q1value')
with p.loop_range(100, 2001, 100) as t_wait:
    p.block_pulse(200, gates, v_init)
    p.ramp(20, gates, v_init, v_manip)

    q1.block_pulse(t_pulse, v_pulse)
    p.wait(t_wait)
    q1.block_pulse(t_pulse, v_pulse)

    p.ramp(100, gates, v_manip, v_read)
    with p.parallel():
        p.set_offsets(gates, v_read)
        p.wait(1000)
        R1.acquire('q1value', 'increment', t_offset=100)
    p.set_offsets(gates, [0.0, 0.0])

p.describe()

p.compile(listing=True, annotate=True)

instrument.run_program(p)

plot_output([qcm0])

if hasattr(qrm1, 'print_acquisitions'):
    # get acquisition timing and counts from Q1Simulator
    qrm1.print_acquisitions()
