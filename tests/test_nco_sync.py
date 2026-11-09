import matplotlib.pyplot as pt
import numpy as np

from q1test import Target, run_interactive

N = 10000


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=200e6)
    instrument.add_control('q2', t.qrm.name, [0, 1], nco_frequency=200e6)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])
    instrument.add_readout('R1', t.qrm.name, [], nco_frequency=200e6)

    t.qrm.in0_gain(0)
    t.qrm.in1_gain(0)

    p = instrument.new_program('nco_sync')
    p.repetitions = 1

    q2 = p.q2
    R1 = p['R1']

    R1.add_acquisition_bins('default', N)
    R1.integration_length_acq = 400

    with p.loop_range(N):
        with p.parallel():
            q2.block_pulse(600, 0.5)
            R1.acquire('default', 'increment', t_offset=160)
            p.wait(1000)
        p.wait(50_000-1620)

    p.compile(listing=True)
    return instrument, p


def test_nco_sync(q1):
    run = q1.run(build)

    data = run.main.get_acquisition_bins('R1', 'default')
    integration_length = run.program.R1.integration_length_acq
    I = np.array(data['integration']['path0'])/integration_length
    Q = np.array(data['integration']['path1'])/integration_length
    assert len(I) == N
    c = I + 1j*Q

    if q1.plotting:
        q1.new_figure('phase')
        pt.plot(np.angle(c)/np.pi)
        pt.title('phase')
        q1.new_figure('amplitude')
        pt.plot(np.abs(c))
        pt.title('amplitude')


if __name__ == "__main__":
    run_interactive(test_nco_sync)
