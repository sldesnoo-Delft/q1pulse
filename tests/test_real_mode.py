from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [0], nco_frequency=50e6, real_mode=True)

    p = instrument.new_program('real_mode')
    p.repetitions = 1

    P1 = p.P1

    P1.ramp_2paths(40, v_start0=0.0, v_end0=0.0, v_start1=0.0, v_end1=0.25)
    P1.block_pulse(200, 0.1, 0.25)
    P1.ramp_2paths(40, v_start0=0.0, v_end0=0.0, v_start1=0.25, v_end1=0.0)

    P1.ramp_2paths(800, v_start0=0.0, v_end0=0.0, v_start1=0.0, v_end1=0.25)
    P1.block_pulse(200, 0.1, 0.25)
    P1.ramp_2paths(820, v_start0=0.0, v_end0=0.0, v_start1=0.25, v_end1=0.0)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_real_mode(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_real_mode)
