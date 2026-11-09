import numpy as np
import pytest

from q1pulse.lang.program_variables import IntVariable, FloatVariable

from q1test import Target, run_interactive, set_mock_data

pytestmark = pytest.mark.isa_v2


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qcm.name, [0])
    instrument.add_readout('R1', t.qrm.name, out_channels=[], in_channels=[0])

    # gain = 0: +/- 0.5V; gain -6 dB: +/- 1.0 V
    t.qrm.in0_gain(0)
    t.qrm.in1_gain(0)

    p = instrument.new_program('event_feedback_acq')
    p.repetitions = 2

    P1 = p.P1
    R1 = p.R1

    n_acq = p.repetitions
    R1.add_acquisition_bins('measurements', n_acq)
    R1.integration_length_acq = 100
    R1.thresholded_acq_threshold = 0.1

    event_tb = p.register_feedback_event("m1_tb")
    event_iq = p.register_feedback_event("m1_iq")

    P1.Rs.m1_tb = IntVariable()
    P1.Rs.m1_i = FloatVariable()
    P1.Rs.m1_q = FloatVariable()

    p.wait(4)
    R1.fb_acq_tb_id(event_tb, wait_after=4)
    R1.fb_acq_iq_id(event_iq, wait_after=4)
    p.P1.block_pulse(100, 0.2)
    p.wait(50)
    R1.acquire('measurements')
    p.wait(650)
    P1.fb_pop_data(event_tb, P1.Rs.m1_tb)
    P1.fb_pop_data(event_iq, P1.Rs.m1_i)
    P1.fb_pop_data(event_iq, P1.Rs.m1_q)
    p.wait(20)

    p.compile(listing=True)

    set_mock_data(instrument, 'R1', 'measurements',
                  np.array([0.2, -0.2]) * R1.integration_length_acq)
    return instrument, p


def test_event_feedback_acq(q1, tmp_path):
    run = q1.run(build)
    run.instrument.save_program(run.program, str(tmp_path))
    assert (tmp_path / 'q1program.json').exists()
    print(run.main.get_variables())


if __name__ == "__main__":
    run_interactive(test_event_feedback_acq)
