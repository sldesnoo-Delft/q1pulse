import pytest

from q1test import Target, count_pulses, run_interactive

REPETITIONS = 3


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])

    p = instrument.new_program('loop_range')
    p.repetitions = REPETITIONS

    P1 = p.P1
    P2 = p.P2

    P1.block_pulse(200, -0.1)
    with p.loop_range(20, 100, 20) as t_wait:
        P1.block_pulse(20, 0.8)
        p.wait(t_wait)
        P2.block_pulse(20, 0.6)
        p.wait(200)

    # 4 pulses
    with p.loop_range(-2, 2, 1):
        P1.block_pulse(20, 0.2)
        p.wait(100)

    p.wait(100)
    # 4 pulses
    with p.loop_range(80, 0, -20) as t_wait:
        P1.block_pulse(20, 0.1)
        p.wait(t_wait + 20)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_loop_range(q1):
    q1.run(build)


@pytest.mark.xfail(reason="DEVNOTES #4: loop_range with negative step has 1 iteration too many",
                   strict=True)
def test_loop_range_pulse_count(q1):
    if not q1.is_simulator:
        pytest.skip("Output can only be checked on the simulator")
    run = q1.run(build, check_listing=False)
    output = run.main.get_output('P1')['P1']
    # QCM output range: +/- 2.5 V. All positive pulses are >= 0.1*2.5 V.
    # 4 pulses per loop, 3 loops.
    # NOTE: by default the simulator only renders the output of 1 repetition.
    assert count_pulses(output, 0.2) == 3 * 4


if __name__ == "__main__":
    run_interactive(test_loop_range)
