from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qrm.name, [0])

    p = instrument.new_program('markers')
    p.repetitions = 1000

    P1 = p.P1
    P2 = p.P2

    with p.parallel():
        P1.block_pulse(20, -0.5)
        P2.block_pulse(20, -0.5)
    p.wait(8)
    with p.parallel():
        P1.set_markers(0b0001)
        P2.set_markers(0b0001)
        P1.block_pulse(20, 0.5)
        P2.block_pulse(20, 0.5)
    P1.set_markers(0b0000)
    P2.set_markers(0b0000)
    p.wait(50_000)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_markers(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_markers)
