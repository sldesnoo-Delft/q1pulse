import matplotlib.pyplot as pt
import numpy as np

from q1test import Target, run_interactive

N = 101


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=200e6)
    instrument.add_readout('rf1', t.qrm.name, [0, 1], nco_frequency=0e6)

    t.qrm.in0_gain(0)
    t.qrm.in1_gain(0)

    amplitude = 0.5
    period = 1000
    f_start = -250e6
    f_stop = 250e6

    p = instrument.new_program('acq_rf_sweep')
    p.repetitions = 1

    q1 = p.q1
    rf1 = p.rf1

    rf1.add_acquisition_bins("default", N)
    rf1.integration_length_acq = 1000
    rf1.nco_prop_delay = 148  # ~ 50 cm line

    q1.set_offset(amplitude, 0.0)
    rf1.set_offset(amplitude)
    rf1.acquire_frequency_sweep(N, period,
                                f_start, f_stop,
                                "default",
                                acq_delay=152)

    rf1.set_offset(0.0)
    q1.set_offset(0.0)

    p.wait(1000)

    p.compile(listing=True)
    return instrument, p


def test_acq_freq_sweep(q1):
    run = q1.run(build)

    data = run.main.get_acquisition_bins('rf1', 'default')
    integration_length = run.program.rf1.integration_length_acq
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
        pt.ylim(0, 0.6)


if __name__ == "__main__":
    run_interactive(test_acq_freq_sweep)
