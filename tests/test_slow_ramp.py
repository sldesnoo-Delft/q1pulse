from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [0])
    instrument.add_control('P2', t.qcm.name, [1])
    instrument.add_control('P3', t.qcm.name, [2])

    p = instrument.new_program('ramp_slow')
    p.repetitions = 2

    P1 = p.P1
    P2 = p.P2
    P3 = p.P3

    c = 1
    with p.parallel():
        # ramp just below stepping limit
        P1.ramp(6580, -0.001*c, 0.001*c)
        # ramp just above stepping limit
        P2.ramp(6580, -0.00101*c, 0.00101*c)
        P3.ramp(6580, -0.0011*c, 0.0011*c)
    p.wait(100)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_slow_ramp(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_slow_ramp)
