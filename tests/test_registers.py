import pytest

from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])

    p = instrument.new_program('registers')

    seq = p.P1

    # just add some waiting time to prevent error messages on real-time executor
    p.wait(1000)
    p.P1.set_offset(0.0)

    p.R.a = 10
    p.R.b = p.R.a + 1
    p.R.b = 5 + p.R.a + 1
    p.R.c = p.R.b + p.R.a
    p.R.c += 5
    p.R.c -= 17
    p.R.d = 1 - p.R.a
    p.R.e = p.R.a << 2
    p.R.f = p.R.a >> 2
    p.R.h = p.R.d >> 2

    # floating point
    p.R.x = 1.0
    p.R.x -= 0.8
    p.R.y = 0.5
    p.R.z = p.R.x - p.R.y

    # sequencer registers
    seq.Rs.x = 9
    seq.Rs.y = seq.Rs.x + p.R.b

    # bitwise
    seq.Rs.a = 0b0011
    seq.Rs.b = seq.Rs.a & 0b0101
    seq.Rs.c = seq.Rs.a | 0b0101
    seq.Rs.d = 0b0101 ^ seq.Rs.a
    seq.Rs.e = ~seq.Rs.a

    p.compile(annotate=True, listing=True, optimize=0)
    return instrument, p


def test_registers(q1):
    run = q1.run(build)
    registers = run.main.get_registers('P1')
    expected = {
        'R.a': 10,
        'R.b': 16,
        'R.c': 14,
        'R.d': -9,
        'R.e': 40,
        'R.f': 2,
        'R.h': -3,
        'R.x': pytest.approx(0.2, abs=1e-6),
        'R.y': pytest.approx(0.5, abs=1e-6),
        'R.z': pytest.approx(-0.3, abs=1e-6),
        'Rs.x': 9,
        'Rs.y': 25,
        'Rs.a': 0b0011,
        'Rs.b': 0b0001,
        'Rs.c': 0b0111,
        'Rs.d': 0b0110,
        'Rs.e': ~0b0011,
        }
    assert registers == expected


if __name__ == "__main__":
    run_interactive(test_registers)
