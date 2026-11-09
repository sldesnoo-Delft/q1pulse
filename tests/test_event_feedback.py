import numpy as np
import pytest

from q1pulse.lang.program_variables import IntVariable

from q1test import Target, run_interactive, set_mock_data

pytestmark = pytest.mark.isa_v2


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qcm.name, [0])
    instrument.add_readout('R1', t.qrm.name, [])

    # gain = 0: +/- 0.5V; gain -6 dB: +/- 1.0 V
    t.qrm.in0_gain(0)
    t.qrm.in1_gain(0)

    p = instrument.new_program('event_feedback')
    p.repetitions = 2

    event_id = p.register_feedback_event("com_data_1")

    P1 = p.P1
    R1 = p.R1

    n_acq = p.repetitions
    R1.add_acquisition_bins('measurements', n_acq)
    R1.integration_length_acq = 100
    R1.thresholded_acq_threshold = 0.1

    p.wait(20)
    R1.acquire('measurements')
    p.wait(10)
    P1.Rs.data = IntVariable()
    R1.fb_com_data(event_id, 77)
    p.wait(500)
    P1.block_pulse(100, 0.2)
    p.wait(100)
    P1.fb_pop_data(event_id, P1.Rs.data)
    p.wait(100)

    p.compile(listing=True)

    set_mock_data(instrument, 'R1', 'measurements',
                  np.array([0.2, -0.2]) * R1.integration_length_acq)
    return instrument, p


def test_event_feedback(q1, tmp_path):
    run = q1.run(build)
    run.instrument.save_program(run.program, str(tmp_path))
    assert (tmp_path / 'q1program.json').exists()
    variables = run.main.get_variables()
    print(variables)
    assert variables['P1']['data'] == 77


if __name__ == "__main__":
    run_interactive(test_event_feedback)
