import pytest

from q1test import Target, run_interactive

N = 100
T_MEASURE = 10_000
T_ACQDELAY = 500


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])
    instrument.add_readout('R1', t.qrm.name, [1])

    p = instrument.new_program('csd_ramp')

    P1 = p.P1
    P2 = p.P2
    R1 = p['R1']  # using alternative notation

    R1.add_acquisition_bins('default', N*N)

    t_step = T_MEASURE + T_ACQDELAY

    with p.loop_linspace(-0.5, 0.5, N) as v2:
        with p.parallel():
            P2.block_pulse(t_step*N, v2)
            P1.ramp(t_step*N, -0.5, 0.5)
            R1.repeated_acquire(N, t_step,
                                'default', 'increment',
                                t_offset=T_ACQDELAY)

    p.compile(annotate=True, listing=True)
    return instrument, p


@pytest.mark.slow
def test_csd_ramp(q1):
    run = q1.run(build)
    data = run.main.get_acquisition_bins('R1', 'default')
    assert len(data['integration']['path0']) == N*N


if __name__ == "__main__":
    run_interactive(test_csd_ramp)
