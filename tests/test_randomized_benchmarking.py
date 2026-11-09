from q1pulse import lsr

from q1test import Target, run_interactive
from test_prng import N, SEED, expected_rnd


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [0])

    p = instrument.new_program('prng_rb')

    P1 = p.P1
    R = P1.Rs

    R.rnd = SEED
    p.wait(200)
    with p.loop_range(N):
        # https://en.wikipedia.org/wiki/Xorshift
        # costs 27 clock ticks = 108 ns
        R.rnd ^= R.rnd << 13
        R.rnd ^= lsr(R.rnd, 17)  # Python has no LSR / unsigned shift right
        R.rnd ^= R.rnd << 5
        P1.log('RND', R.rnd, time=True)
        # Multiply with 3 and use top 5 bits. (64 ns)
        R.clifford = lsr(lsr(R.rnd, 2) + lsr(R.rnd, 1), 27)
        P1.log('CLF', R.clifford, time=True)
        P1.block_pulse(80+108+64, R.rnd.asfloat())

    p.compile(annotate=True, listing=True)
    return instrument, p


def test_randomized_benchmarking(q1):
    run = q1.run(build)
    registers = run.main.get_registers('P1')
    assert registers['Rs.rnd'] == expected_rnd(N)


if __name__ == "__main__":
    run_interactive(test_randomized_benchmarking)
