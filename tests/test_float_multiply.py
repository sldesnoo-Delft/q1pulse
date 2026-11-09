"""Multiplication of fixed point "float" values.

Floats are stored as 32-bit fixed point values in the range [-1.0, 1.0].
"""
import pytest

from q1test import Target, run_interactive

# Q1ASM v1 has no multiply instructions.
pytestmark = pytest.mark.isa_v2

# Results have 30 bits precision. See Multiply._evaluate().
TOLERANCE = 1e-6


def build_multiply(a, b, rhs_literal=False, lhs_literal=False):
    def build(t: Target):
        # Functional test without reference listing.
        instrument = t.new_instrument(listing=False)
        instrument.add_qcm(t.qcm)
        instrument.add_control('P1', t.qcm.name, [2])

        p = instrument.new_program('float_multiply')

        # some output to avoid that the program is skipped
        p.wait(100)
        p.P1.set_offset(0.0)

        p.R.a = a
        if rhs_literal:
            p.R.result = p.R.a * b
        elif lhs_literal:
            p.R.result = b * p.R.a
        else:
            p.R.b = b
            p.R.result = p.R.a * p.R.b

        p.compile(optimize=0)
        return instrument, p
    return build


xfail_minus_one = pytest.mark.xfail(
    reason="DEVNOTES #10: -1.0 * -1.0 overflows to -1.0", strict=True)
xfail_negative_literal = pytest.mark.xfail(
    reason="DEVNOTES #11: negative float literal is invalid immediate for muls32h", strict=True)


@pytest.mark.parametrize("a, b", [
    (0.5, 0.5),
    (-0.5, -0.5),
    (-1.0, 0.5),
    (0.25, -0.75),
    (1.0, 1.0),
    (1.0, -1.0),
    (-1.0, 1.0),
    (-1.0, -0.999),
    (-0.999, -0.999),
    (0.0, -1.0),
    (1e-4, 1e-4),
    pytest.param(-1.0, -1.0, marks=xfail_minus_one),
    ])
def test_register_register(q1, a, b):
    run = q1.run(build_multiply(a, b), check_listing=False)
    result = run.main.get_registers('P1')['R.result']
    assert result == pytest.approx(a * b, abs=TOLERANCE)


@pytest.mark.parametrize("a, b", [
    (0.5, 0.5),
    (-0.5, 0.5),
    (-1.0, 1.0),
    (1.0, 0.001),
    pytest.param(0.5, -0.5, marks=xfail_negative_literal),
    pytest.param(0.5, -1.0, marks=xfail_negative_literal),
    pytest.param(0.5, -0.001, marks=xfail_negative_literal),
    ])
def test_register_literal(q1, a, b):
    run = q1.run(build_multiply(a, b, rhs_literal=True), check_listing=False)
    result = run.main.get_registers('P1')['R.result']
    assert result == pytest.approx(a * b, abs=TOLERANCE)


@pytest.mark.parametrize("a, b", [
    (0.5, 0.5),
    (-0.5, 0.5),
    pytest.param(0.5, -0.5, marks=xfail_negative_literal),
    ])
def test_literal_register(q1, a, b):
    run = q1.run(build_multiply(a, b, lhs_literal=True), check_listing=False)
    result = run.main.get_registers('P1')['R.result']
    assert result == pytest.approx(a * b, abs=TOLERANCE)

# %%
if __name__ == "__main__":
    run_interactive(test_register_register, a=-0.5, b=-0.5)
    run_interactive(test_register_register, a=-1.0, b=-1.0)
