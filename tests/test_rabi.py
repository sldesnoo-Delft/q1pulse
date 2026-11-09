import numpy as np

from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=200e6)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])
    instrument.add_readout('R1', t.qrm.name, [], nco_frequency=200e6)
    instrument.add_control('Ro1', t.qrm.name, [0, 1], nco_frequency=200e6)

    t.qrm.in0_gain(0)
    t.qrm.in1_gain(0)

    p = instrument.new_program('rabi')
    p.repetitions = 2

    q1 = p.q1
    R1 = p['R1']
    Ro1 = p['Ro1']

    R1.add_acquisition_bins('default', 20)
    R1.integration_length_acq = 400

    gates = ['P1', 'P2']
    v_init = [0.220, 0.040]
    v_manip = [0.0, 0.0]
    v_read = [-0.050, 0.060]
    rabi_amplitude = 0.1
    readout_amplitude = 0.1

    R1.reset_bin_counter('default')
    with p.loop_range(100, 2001, 100) as t_pulse:
        # init
        p.block_pulse(200, gates, v_init)
        p.wait(20)
        # manip
        q1.block_pulse(t_pulse, rabi_amplitude)
        # read
        p.ramp(200, gates, v_manip, v_read)
        with p.parallel():
            p.set_offsets(gates, v_read)
            Ro1.block_pulse(600, readout_amplitude)
            R1.acquire('default', 'increment', t_offset=100)
            p.wait(1000)
        p.wait(1000)

    p.set_offsets(gates, [0.0, 0.0])

    p.compile(listing=True)
    return instrument, p


def test_rabi(q1):
    run = q1.run(build)

    data = run.main.get_acquisition_bins('R1', 'default')
    I = data['integration']['path0']
    Q = data['integration']['path1']
    assert len(I) == 20
    for i in range(20):
        c = I[i] + 1j*Q[i]
        print(f'{I[i]:6.3f}, {Q[i]:6.3f}, {abs(c):6.3f}, {np.angle(c)/np.pi:5.3f}')


if __name__ == "__main__":
    run_interactive(test_rabi)
