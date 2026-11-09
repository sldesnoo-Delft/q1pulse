import pytest

from q1pulse.lang.program_variables import IntVariable, FloatVariable

from q1test import Target, run_interactive

pytestmark = pytest.mark.isa_v2


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])

    p = instrument.new_program('variables')

    seq = p.P1

    # just add some waiting time to prevent error messages on real-time executor
    p.wait(1000)
    p.P1.set_offset(0.0)

    p.R.a = IntVariable(init_scope='load', initial_value=10)  # Name is "a"
    p.R.b = IntVariable()
    p.R.c = IntVariable()

    p.R.b = p.R.a + 1
    p.R.b = 5 + p.R.a + 1
    p.R.c = p.R.a * p.R.b

    # floating point
    p.R.x = FloatVariable(init_scope="load", initial_value=1.0)
    p.R.x -= 0.8
    p.R.y = FloatVariable()
    p.R.y = 0.5
    p.R.z = p.R.x - p.R.y

    # sequencer registers
    seq.Rs.p1 = 9
    seq.Rs.q1 = seq.Rs.p1 + p.R.b
    seq.Rs.v1 = IntVariable(init_scope="load", initial_value=0)
    seq.Rs.v1 = seq.Rs.q1 + p.R.a
    seq.Rs.v2 = FloatVariable()
    seq.Rs.v2 = p.R.x * p.R.y

    # bitwise
    seq.Rs.a1 = 0b0011
    seq.Rs.b1 = seq.Rs.a1 & 0b0101
    seq.Rs.c1 = seq.Rs.a1 | 0b0101
    seq.Rs.d1 = 0b0101 ^ seq.Rs.a1
    seq.Rs.e1 = ~seq.Rs.a1

    p.compile(annotate=True, listing=True, optimize=0)
    return instrument, p


def test_variables(q1):
    run = q1.prepare(build)

    run.execute()
    variables = run.main.get_variables()['P1']
    assert variables['a'] == 10
    assert variables['b'] == 16
    assert variables['c'] == 160
    assert variables['x'] == pytest.approx(0.2, abs=1e-6)
    assert variables['y'] == pytest.approx(0.5, abs=1e-6)
    assert run.main.get_registers('P1')['R.z'] == pytest.approx(-0.3, abs=1e-6)
    assert variables['v1'] == 35
    assert variables['v2'] == pytest.approx(0.1, abs=1e-6)

    run.execute(variables={"a": -2, "x": 0.0}, label="a=-2, x=0.0")
    variables = run.main.get_variables()['P1']
    assert variables['a'] == -2
    assert variables['b'] == 4
    assert variables['c'] == -8
    assert variables['x'] == pytest.approx(-0.8, abs=1e-6)
    assert variables['v1'] == 11
    assert variables['v2'] == pytest.approx(-0.4, abs=1e-6)


if __name__ == "__main__":
    run_interactive(test_variables)
