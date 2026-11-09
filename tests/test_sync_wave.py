"""Check synchronization of waveforms on an oscilloscope.

The program runs on hardware for SCOPE_TIME seconds.
The simulator reference only runs a few iterations.
"""
import numpy as np
import pytest

from q1test import Target, run_interactive
from test_sync import run_on_scope

pytestmark = pytest.mark.hw_only

N = 10
RAMPED = False


def build(t: Target):
    # Do not specify path. This is not a Q1ASM reference test.
    instrument = t.new_instrument(listing=False)
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qcm.name, [0])
    instrument.add_control('P2', t.qcm.name, [1])

    p = instrument.new_program('sync_wave')
    p.repetitions = 1 if t.is_simulator else 10_000_000

    P1 = p.P1
    P2 = p.P2

    if RAMPED:
        block = np.concatenate([
                np.linspace(0, -0.5, 2, endpoint=False),
                -0.5*np.ones(N-4),
                np.linspace(-0.5, 0.5, 4, endpoint=False),
                0.5*np.ones(N-4),
                np.linspace(0.5, 0, 2, endpoint=False),
                ])
    else:
        block = np.concatenate([
                -0.5*np.ones(N),
                0.5*np.ones(N),
                ])

    P1.add_wave('block', block)
    P2.add_wave('block', block)
    P1.set_gain(1.0)
    P2.set_gain(1.0)

    with p.loop_range(2):
        with p.parallel():
            P1.play('block')
            P2.play('block')
            p.wait(2*N)
    p.wait(10000)

    p.compile()
    return instrument, p


def test_sync_wave(q1):
    run_on_scope(q1, build)


if __name__ == "__main__":
    run_interactive(test_sync_wave)
