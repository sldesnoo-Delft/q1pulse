from q1test import Target, run_interactive

N = 100


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])
    instrument.add_readout('R1', t.qrm.name, [1])

    p = instrument.new_program('csd')

    P1 = p.P1
    P2 = p.P2
    R1 = p['R1']  # using alternative notation

    R1.add_acquisition_bins('default', N*N)

    t_measure = 2000
    t_acqdelay = 500
    t_step = t_measure + t_acqdelay

    with p.loop_linspace(-0.5, 0.5, N) as v2:
        with p.loop_linspace(-0.5, 0.5, N) as v1:
            with p.parallel():
                p.wait(t_step)
                P2.set_offset(v2)
                P1.set_offset(v1)
                R1.acquire('default', 'increment', t_offset=t_acqdelay)

    P1.set_offset(0.0)
    P2.set_offset(0.0)

    p.compile(annotate=True, listing=True)
    return instrument, p


def test_csd(q1):
    run = q1.run(build)
    data = run.main.get_acquisition_bins('R1', 'default')
    assert len(data['integration']['path0']) == N*N


if __name__ == "__main__":
    run_interactive(test_csd)
