import pytest

from q1pulse.lang.program_variables import IntVariable

from q1test import Target, run_interactive

pytestmark = pytest.mark.isa_v2


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [0])

    p = instrument.new_program('if_rt_2seq')

    P1 = p.P1
    P2 = p.P2

    # just add some waiting time to prevent error messages on real-time executor
    p.wait(80)
    P1.block_pulse(10, 0.1)
    p.wait(10)

    p.R.a = IntVariable(init_scope='load', initial_value=10)  # Name is "a"
    p.R.b = IntVariable(init_scope='load', initial_value=10)
    p.R.c = IntVariable()
    p.R.d = IntVariable()

    p.R.d = 0
    p.R.c = 1

    with P2.if_(p.R.a > p.R.c):
        p.R.c = 10

    with p.if_(p.R.a == p.R.b):
        p.R.d = 2
        P1.block_pulse(100, 0.2)
    with p.elif_(p.R.a < p.R.b):
        p.R.d = 3
        P1.wait(20)
        P1.block_pulse(10, 0.4)
    with p.else_:
        p.R.d = 4
        P1.wait(10)
        P1.block_pulse(80, 0.6)

    p.wait(10)
    P1.block_pulse(20, -0.2)
    P2.block_pulse(20, -0.2)
    p.wait(10)

    p.compile(annotate=True, listing=True, optimize=0)
    return instrument, p


@pytest.mark.parametrize("a, c_p2, d", [(10, 10, 2), (0, 1, 3), (20, 10, 4)])
def test_if_rt_2seq(q1, a, c_p2, d):
    run = q1.prepare(build)
    run.execute(variables={"a": a}, label=f"a={a}")
    variables = run.main.get_variables()
    # The condition of P2.if_() is only evaluated on P2.
    # NOTE: P1 executes the assignment `p.R.c = 10` unconditionally. See DEVNOTES #9.
    assert variables['P2']['c'] == c_p2
    assert variables['P1']['d'] == d
    assert variables['P2']['d'] == d


if __name__ == "__main__":
    run_interactive(test_if_rt_2seq, a=0, c_p2=1, d=3)
