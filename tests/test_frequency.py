from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])

    p = instrument.new_program('frequency')
    p.repetitions = 2

    P1 = p.P1
    P1.nco_frequency = 1e6

    p.R.frequency = int(12e6)
    P1.Rs.frequency = int(30e6)

    P1.set_offset(0.5)
    P1.set_frequency(10e6)
    p.wait(100)
    P1.set_frequency(5e6)
    p.wait(100)
    P1.set_frequency(p.R.frequency)
    p.wait(100)
    P1.set_frequency(P1.Rs.frequency)
    p.wait(100)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_frequency(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_frequency)
