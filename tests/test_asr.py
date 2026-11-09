from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])

    p = instrument.new_program('asr')

    p.R.a = 9
    p.R.b = 2

    p.R.c = p.R.a >> 2

    p.R.d = p.R.a >> p.R.b

    p.R.e = -9
    p.R.f = p.R.e >> 1  # q1asm evaluation
    p.R.h = -9 >> 1     # Python evaluation

    p.compile(annotate=True, listing=True, optimize=0)
    return instrument, p


def test_asr(q1):
    run = q1.run(build)
    registers = run.main.get_registers('P1')
    assert registers['R.c'] == 2
    assert registers['R.d'] == 2
    assert registers['R.e'] == -9
    assert registers['R.f'] == -5
    assert registers['R.h'] == -5


if __name__ == "__main__":
    run_interactive(test_asr)
