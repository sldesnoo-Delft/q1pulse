import matplotlib.pyplot as pt
import numpy as np

from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=0)

    p = instrument.new_program('frequency_phase')
    p.repetitions = 1

    q1 = p.q1

    q1.set_offset(1.0)
    q1.set_frequency(10e6)
    p.wait(100)
    q1.shift_phase(0.5)
    p.wait(100)
    q1.set_offset(0.0)
    q1.shift_phase(-0.5)
    p.wait(100)
    q1.set_phase(0.0)
    q1.set_offset(1.0)
    q1.set_offset(1.0)
    q1.set_frequency(-10e6)
    p.wait(100)
    q1.shift_phase(0.5)
    p.wait(100)
    q1.set_offset(0.0)
    p.wait(20)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_frequency_phase(q1):
    run = q1.run(build)

    if q1.plotting:
        output = run.simulation.get_output('q1')
        phase = np.angle(output['q1-I'] + 1j*output['q1-Q'])
        q1.new_figure('phase')
        pt.plot(phase, label='phase')
        pt.grid()
        pt.legend()


if __name__ == "__main__":
    run_interactive(test_frequency_phase)
