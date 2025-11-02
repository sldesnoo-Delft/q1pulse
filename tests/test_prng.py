
from q1pulse import Q1Instrument, lsr

from init_pulsars import qcm0
from plot_util import plot_output

instrument = Q1Instrument('q1')
instrument.add_qcm(qcm0)
instrument.add_control('P1', qcm0.name, [0])

p = instrument.new_program('prng')
P1 = p.P1

R = P1.Rs

seed = 1
R.rnd = seed
p.wait(100)
with p.loop_range(10):
    # https://en.wikipedia.org/wiki/Xorshift
    # costs 27 clock ticks = 108 ns
    R.rnd ^= R.rnd << 13
    R.rnd ^= lsr(R.rnd, 17) # Python has no LSR / unsigned shift right
    R.rnd ^= R.rnd << 5
    P1.log('RND', R.rnd, time=True)
    P1.block_pulse(80+108, R.rnd.asfloat())


p.describe()

p.compile(annotate=True, listing=True)

instrument.run_program(p)

plot_output([qcm0])


# Python implementation of xorshift32
def rnd(x):
    x ^= (x << 13) & 0xFFFF_FFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFF_FFFF
    return x


x = 1
for i in range(10):
    x = rnd(x)
    print(f'{x:08X}')
