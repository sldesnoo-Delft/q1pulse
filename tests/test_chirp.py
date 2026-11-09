from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=0)

    p = instrument.new_program('chirp')
    p.repetitions = 1

    q1 = p.q1

    q1.chirp(20_000, 0.5, 1e6, 10e6)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_chirp(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_chirp)
