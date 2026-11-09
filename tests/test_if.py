import pytest

from q1pulse.lang.program_variables import IntVariable

from q1test import Target, run_interactive

pytestmark = pytest.mark.isa_v2


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])

    p = instrument.new_program('if')

    # just add some waiting time to prevent error messages on real-time executor
    p.wait(1000)
    p.P1.set_offset(0.0)

    p.R.a = IntVariable(init_scope='load', initial_value=10)  # Name is "a"
    p.R.b = IntVariable(init_scope='load', initial_value=10)
    p.R.c = IntVariable()
    p.R.d = IntVariable()

    p.R.d = 0
    p.R.c = 1

    with p.if_(p.R.a > p.R.b):
        p.R.c = 10

    with p.if_(10 == p.R.a):
        p.R.c += 100

    with p.if_(p.R.a == p.R.b):
        p.R.d = 2
    with p.elif_(p.R.a < p.R.b):
        p.R.d = 3
    with p.else_:
        p.R.d = 4

    with p.if_(p.R.a):
        p.R.d += 10

    with p.if_(p.R.a >> 4):
        p.R.d += 100

    p.compile(annotate=True, listing=True, optimize=0)
    return instrument, p


def test_if(q1):
    run = q1.prepare(build)

    # a == b == 10
    run.execute()
    variables = run.main.get_variables()['P1']
    assert variables['c'] == 101
    assert variables['d'] == 12

    run.execute(variables={"a": 0}, label="a=0")
    variables = run.main.get_variables()['P1']
    assert variables['c'] == 1
    assert variables['d'] == 3

    run.execute(variables={"a": 20}, label="a=20")
    variables = run.main.get_variables()['P1']
    assert variables['c'] == 10
    assert variables['d'] == 114


if __name__ == "__main__":
    run_interactive(test_if)
