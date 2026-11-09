from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=25e6)

    p = instrument.new_program('loops')
    p.repetitions = 3

    P1 = p.P1
    P2 = p.P2
    q1 = p.q1

    with p.loop_linspace(0.2, 1.0, 5) as amplitude:
        P1.block_pulse(20, amplitude)
        P2.block_pulse(100, amplitude - 0.1)
        q1.block_pulse(40, amplitude - 0.1)
        q1.shift_phase(0.5)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_loops(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_loops)
