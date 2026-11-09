from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=0)
    instrument.add_control('P1', t.qcm.name, [2], nco_frequency=0)

    p = instrument.new_program('chirp_1ns')
    p.repetitions = 1

    q1 = p.q1
    P1 = p.P1

    P1.block_pulse(7, 0.2)
    q1.chirp(1000, 0.5, 10e6, 40e6)

    P1.block_pulse(7, 0.2)
    q1.chirp(999, 0.5, 10e6, 40e6)

    P1.block_pulse(7, 0.2)
    q1.chirp(998, 0.5, 10e6, 40e6)

    P1.block_pulse(7, 0.2)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_chirp_1ns(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_chirp_1ns)
