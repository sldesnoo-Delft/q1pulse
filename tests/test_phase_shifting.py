import matplotlib.pyplot as pt
import numpy as np

from q1test import Target, run_interactive

N = 1000


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qcm.name, [0])
    instrument.add_control('q1', t.qrm.name, [0, 1], nco_frequency=200e6)
    instrument.add_readout('R1', t.qrm.name, [], nco_frequency=200e6)

    t.qrm.in0_gain(0)
    t.qrm.in1_gain(0)

    p = instrument.new_program('phase_shifting')
    p.repetitions = 1

    q1 = p.q1
    R1 = p.R1

    R1.add_acquisition_bins('default', N)
    R1.integration_length_acq = 500

    rabi_amplitude = 0.1
    q1.Rs.phase_shift = 0.001
    p.R.bin = 0

    with p.loop_range(N):
        with p.parallel():
            q1.block_pulse(600, rabi_amplitude)
            R1.acquire('default', p.R.bin, t_offset=120)
            p.R.bin += 1
        # for small phase shifts in register use hires_reg=True
        q1.shift_phase(q1.Rs.phase_shift, hires_reg=True)
        p.wait(500)

    p.compile(listing=True)
    return instrument, p


def test_phase_shifting(q1):
    run = q1.run(build)

    data = run.main.get_acquisition_bins('R1', 'default')
    I = np.array(data['integration']['path0'])
    Q = np.array(data['integration']['path1'])
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
    run_interactive(test_phase_shifting)
