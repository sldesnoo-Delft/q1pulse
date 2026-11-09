import numpy as np

from q1test import Target, run_interactive, set_mock_data
from test_acquire import N, V1_MAX, V2_MAX, build_acquire, get_acquired_data


def mock_data(repetitions):
    data0 = np.linspace(-V1_MAX, V1_MAX, N).repeat(N)
    data1 = np.tile(np.linspace(-V2_MAX, V2_MAX, N), N)
    return np.tile(data0, repetitions), np.tile(data1, repetitions)


def build(t: Target):
    instrument, p = build_acquire(t, 'acquire_mocked', in_channels=[])
    integration_length = p.R1.integration_length_acq
    data0, data1 = mock_data(p.repetitions)
    # Mock data is only set on simulator.
    set_mock_data(instrument, 'R1', 'non-weighed',
                  np.array([data0, data1]).T * integration_length)
    set_mock_data(instrument, 'R1', 'weighed', (data0 + 1j*data1)/2)
    return instrument, p


def test_acquire_mock_data(q1):
    run = q1.run(build)
    dn0, dn1, dw0, dw1 = get_acquired_data(run.main)
    with np.printoptions(precision=2, threshold=1000):
        print('non-weighed')
        print(dn0)
        print(dn1)
        print('weighed')
        print(dw0)
        print(dw1)

    if q1.is_simulator:
        data0, data1 = mock_data(run.program.repetitions)
        shape = dn0.shape
        vmax_in = 0.5
        np.testing.assert_allclose(dn0, data0.reshape(shape)*vmax_in, atol=1e-3)
        np.testing.assert_allclose(dn1, data1.reshape(shape)*vmax_in, atol=1e-3)
        np.testing.assert_allclose(dw0, data0.reshape(shape)/2*vmax_in, atol=1e-3)
        np.testing.assert_allclose(dw1, data1.reshape(shape)/2*vmax_in, atol=1e-3)


if __name__ == "__main__":
    run_interactive(test_acquire_mock_data)
