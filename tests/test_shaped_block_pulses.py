import numpy as np

from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=100e6)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])
    instrument.add_readout('R1', t.qrm.name, [])

    p = instrument.new_program('shaped_block')
    p.repetitions = 2

    q1 = p.q1
    P1 = p.P1
    R1 = p.R1

    block80 = q1.add_wave('block80', np.ones(80))
    block80 = P1.add_wave('block80', np.ones(80))
    R1.add_acquisition_bins('acq_bins', p.repetitions)
    R1.integration_length_acq = 80

    p.R.wait = 20

    with p.loop_range(4):
        q1.shaped_pulse(block80, 0.5, block80, 0.5)
        P1.shaped_pulse(block80, 0.1)
        p.wait(20)
        p.wait(p.R.wait)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_shaped_block_pulses(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_shaped_block_pulses)
