from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])

    p = instrument.new_program('baseband')
    p.repetitions = 3

    P1 = p.P1
    P2 = p.P2

    p.R.amplitude = 0.125
    P1.Rs.amplitude = -0.125

    P1.block_pulse(200, p.R.amplitude)
    P1.block_pulse(200, P1.Rs.amplitude)
    P1.block_pulse(200, p.R.amplitude + 0.5)
    p.wait(1000)
    P1.block_pulse(100, 0.5)
    P2.block_pulse(100, -0.5)

    p.wait(1000)
    with p.parallel():
        P1.block_pulse(100, 0.25)
        P2.block_pulse(100, -0.25)

    p.add_comment('--- long wait')
    p.wait(100_000)
    P1.block_pulse(500, -1.0)
    p.add_comment('--- longer wait')
    p.wait(160_000)
    P1.block_pulse(500, 0.5)
    p.add_comment('--- very long wait')
    p.wait(500_000)
    P1.block_pulse(1000, 0.75)
    P2.block_pulse(1000, -0.75)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_baseband(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_baseband)
