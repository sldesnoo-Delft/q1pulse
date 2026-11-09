import scipy.signal as signal

from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=100e6)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])
    instrument.add_readout('R1', t.qrm.name, [])

    p = instrument.new_program('shaped')
    p.repetitions = 2

    q1 = p.q1
    P1 = p.P1
    P2 = p.P2
    R1 = p.R1

    gauss80 = q1.add_wave('gauss80', signal.windows.gaussian(80, std=0.12 * 80))
    tukey100 = P1.add_wave('tukey100', signal.windows.tukey(100, 0.5))
    R1.add_acquisition_bins('acq_bins', p.repetitions)
    R1.integration_length_acq = 80

    amplitude = 0.125

    q1.shaped_pulse(gauss80, 0.4, gauss80, 0.4)
    p.wait(20)
    P1.shaped_pulse(tukey100, 0.1)
    p.wait(20)
    q1.shaped_pulse('gauss80', amplitude, 'gauss80', amplitude)
    p.wait(40)
    with p.parallel():
        P1.block_pulse(100, 0.25)
        P2.block_pulse(100, -0.25)
        q1.shaped_pulse(gauss80, amplitude)
        R1.acquire('acq_bins', 'increment')

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_shaped_pulses(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_shaped_pulses)
