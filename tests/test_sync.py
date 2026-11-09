"""Check synchronization of outputs on an oscilloscope.

The program runs on hardware for SCOPE_TIME seconds.
The simulator reference only runs a few iterations.
"""
import time

import pytest

from q1test import Target, run_interactive

SCOPE_TIME = 10  # seconds

pytestmark = pytest.mark.hw_only


def build(t: Target):
    # Do not specify path. This is not a Q1ASM reference test.
    instrument = t.new_instrument(listing=False)
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qrm.name, [0])
    instrument.add_control('P2', t.qcm.name, [1])
    instrument.add_control('P3', t.qcm.name, [2])
    instrument.add_control('P4', t.qcm.name, [3])
    instrument.add_control('R1', t.qrm.name, [1])

    p = instrument.new_program('sync')
    p.repetitions = 1 if t.is_simulator else 10_000_000

    a = 1.0
    t_step = 5000
    gates = ['P1', 'P2', 'P3', 'P4', 'R1']
    n_loop = 2 if t.is_simulator else 1000

    with p.loop_range(n_loop):
        p.set_offsets(gates, [-a]*5)
        p.wait(t_step)
        p.set_offsets(gates, [a]*5)
        p.wait(t_step)

    p.compile()
    return instrument, p


def run_on_scope(q1, build):
    run = q1.prepare(build, check_listing=False)
    if q1.is_simulator:
        # Only a few iterations on the simulator. See build().
        run.execute()
        return
    if run.reference is not None:
        run.reference.execute()
    q1.plot(run)
    run.instrument.start_program(run.program)
    try:
        time.sleep(SCOPE_TIME)
    finally:
        run.instrument.stop_program()


def test_sync(q1):
    run_on_scope(q1, build)


if __name__ == "__main__":
    run_interactive(test_sync)
