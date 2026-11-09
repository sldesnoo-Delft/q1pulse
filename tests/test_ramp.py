from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])

    p = instrument.new_program('ramp')
    p.repetitions = 2

    P1 = p.P1
    P2 = p.P2

    P1.block_pulse(40, -0.25)
    P2.ramp(40, 0.0, 1.0)
    P1.block_pulse(40, 0.5)
    p.wait(20)
    P1.ramp(320, 0.0, 0.8)
    P1.ramp(200, 0.8, 0.4)
    with p.parallel():
        P2.ramp(152, -0.5, -1.0)
        P1.ramp(100, -0.5, -1.0)
        P1.ramp(52, -1.0, -0.5, t_offset=100)
    P2.ramp(40, -1.0, -0.2)
    P2.ramp(104, 0.0, 2**-14)
    P1.ramp(104, 0.0, 1.01*2**-15)
    P1.ramp(104, 0.0, 1.00*2**-15)
    P1.ramp(104, 0.0, 0.99*2**-15)
    P1.ramp(100000, 0.0, 2**-14)
    P1.ramp(100000, 0.0, 2**-15)
    p.wait(100)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_ramp(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_ramp)
