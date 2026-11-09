from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])

    p = instrument.new_program('phase')
    p.repetitions = 100

    P1 = p.P1

    p.R.phase1 = 0.125
    P1.Rs.phase2 = -0.125
    p.wait(60)
    P1.set_phase(0.5)

    p.wait(348)
    P1.set_phase(p.R.phase1)

    p.wait(188)
    P1.shift_phase(P1.Rs.phase2, hires_reg=False)

    p.wait(348)
    P1.shift_phase(P1.Rs.phase2 + 0.1)

    # optimize=0: P1 has no IO instructions. Do not skip execution.
    p.compile(listing=True, annotate=True, optimize=0)
    return instrument, p


def test_phase(q1):
    run = q1.run(build)
    # Registers must not be modified by phase conversion.
    registers = run.main.get_registers('P1')
    assert abs(registers['R.phase1'] - 0.125) < 1e-6
    assert abs(registers['Rs.phase2'] + 0.125) < 1e-6


if __name__ == "__main__":
    run_interactive(test_phase)
