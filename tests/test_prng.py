from q1pulse import lsr

from q1test import Target, run_interactive

N = 10
SEED = 1


def xorshift32(x):
    """Python implementation of xorshift32."""
    x ^= (x << 13) & 0xFFFF_FFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFF_FFFF
    return x


def expected_rnd(n, seed=SEED):
    """Returns the expected random value after n iterations as signed int."""
    x = seed
    for _ in range(n):
        x = xorshift32(x)
    return x - (1 << 32) if x & 0x8000_0000 else x


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [0])

    p = instrument.new_program('prng')

    P1 = p.P1
    R = P1.Rs

    R.rnd = SEED
    p.wait(100)
    with p.loop_range(N):
        # https://en.wikipedia.org/wiki/Xorshift
        # costs 27 clock ticks = 108 ns
        R.rnd ^= R.rnd << 13
        R.rnd ^= lsr(R.rnd, 17)  # Python has no LSR / unsigned shift right
        R.rnd ^= R.rnd << 5
        P1.log('RND', R.rnd, time=True)
        P1.block_pulse(80+108, R.rnd.asfloat())

    p.compile(annotate=True, listing=True)
    return instrument, p


def test_prng(q1):
    run = q1.run(build)
    registers = run.main.get_registers('P1')
    assert registers['Rs.rnd'] == expected_rnd(N)


if __name__ == "__main__":
    run_interactive(test_prng)
