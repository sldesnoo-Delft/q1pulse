import numpy as np

from q1test import Target, run_interactive, set_mock_data


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qcm.name, [0])
    instrument.add_readout('R1', t.qrm.name, [])

    # gain = 0: +/- 0.5V; gain -6 dB: +/- 1.0 V
    t.qrm.in0_gain(0)
    t.qrm.in1_gain(0)

    p = instrument.new_program('feedback')
    p.repetitions = 2

    trigger1 = p.configure_trigger('R1')
    counter1 = p.add_trigger_counter(trigger1)

    P1 = p.P1
    R1 = p.R1

    n_acq = p.repetitions
    R1.add_acquisition_bins('measurements', n_acq)
    R1.integration_length_acq = 100
    R1.thresholded_acq_threshold = 0.1

    R1.acquire('measurements')
    p.wait(20)
    p.latch_reset()
    p.wait(20)
    P1.latch_enable(True)
    p.wait(60)
    P1.set_markers(0b1111)
    P1.ramp(60, -0.5, -0.25)
    p.wait(40)
    P1.set_markers(0b0000)
    P1.ramp(60, 0.25, 0.5)
    p.wait(120)
    with P1.conditional([counter1], evaluation_time=20) as flags:
        with flags.all_set():
            P1.ramp(60, 0.25, 0.25)
        with flags.none_set():
            P1.ramp(60, 0.25, 0.0)
    p.wait(40)
    with p.conditional([counter1]) as flags:
        with flags.all_set():
            P1.ramp(60, 0.25, 0.25)
    p.wait(40)
    P1.ramp(60, 0.25, 0.5)
    p.wait(20)
    P1.latch_enable(False)
    p.wait(20)

    p.compile(listing=True)

    set_mock_data(instrument, 'R1', 'measurements',
                  np.array([0.2, -0.2]) * R1.integration_length_acq)
    return instrument, p


def test_feedback(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_feedback)
