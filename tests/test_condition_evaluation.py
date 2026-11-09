import pytest

from q1pulse.lang.program_variables import IntVariable

from q1test import Target, run_interactive

pytestmark = pytest.mark.isa_v2


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])

    p = instrument.new_program('bool_evaluation')

    # just add some waiting time to prevent error messages on real-time executor
    p.wait(1000)
    p.P1.set_offset(0.0)

    p.R.a = IntVariable(init_scope='load', initial_value=10)  # Name is "a"
    p.R.b = IntVariable(init_scope='load', initial_value=20)
    p.R.c = IntVariable()
    p.R.d = IntVariable()

    p.R.d = 0
    p.R.c = 1

    p.R.c = (p.R.a > p.R.b)

    p.R.d = (p.R.a > p.R.b) & (p.R.a > p.R.c)

    p.compile(annotate=True, listing=True, optimize=0)
    return instrument, p


def test_condition_evaluation(q1):
    run = q1.prepare(build)

    run.execute()
    variables = run.main.get_variables()['P1']
    assert variables['c'] == 0
    assert variables['d'] == 0

    run.execute(variables={"a": 30}, label="a=30")
    variables = run.main.get_variables()['P1']
    assert variables['c'] == 1
    assert variables['d'] == 1


@pytest.mark.xfail(reason="DEVNOTES #2: integer comparisons are unsigned", strict=True)
def test_condition_evaluation_negative(q1):
    run = q1.prepare(build)
    run.execute(variables={"a": -2}, label="a=-2")
    variables = run.main.get_variables()['P1']
    assert variables['c'] == 0
    assert variables['d'] == 0


if __name__ == "__main__":
    run_interactive(test_condition_evaluation)
