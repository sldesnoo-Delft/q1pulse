import numpy as np
import scipy.signal as signal

from q1test import Target, run_interactive

N = 5

# output range QCM (P1): +/- 2.5 V
# output range QRM (P1): +/- 0.5 V
# input range QRM (R1): +/- 0.5 V (gain = 0 dB)
V1_MAX = 0.4/2.5
V2_MAX = 0.4/0.5


def build_acquire(t: Target, program_name='acquire', in_channels=[0, 1]):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qcm.name, [0])
    instrument.add_control('P2', t.qrm.name, [1])
    instrument.add_control('P2c', t.qcm.name, [1])
    instrument.add_readout('R1', t.qrm.name, [], in_channels=in_channels)

    # gain = 0: +/- 0.5V; gain -6 dB: +/- 1.0 V
    t.qrm.in0_gain(0)
    t.qrm.in1_gain(0)

    p = instrument.new_program(program_name)
    p.repetitions = 1

    P1 = p.P1
    P2 = p.P2
    P2c = p.P2c
    R1 = p.R1

    n_acq = N*N*p.repetitions
    R1.add_acquisition_bins('non-weighed', n_acq)
    R1.add_acquisition_bins('weighed', n_acq)
    R1.add_weight('gaus100', signal.windows.gaussian(100, 12))
    R1.integration_length_acq = 100

    with p.loop_linspace(-V1_MAX, V1_MAX, N) as v1:
        with p.loop_linspace(-V2_MAX, V2_MAX, N) as v2:
            with p.parallel():
                P1.block_pulse(500, v1)
                P2.block_pulse(500, v2)
                P2c.block_pulse(500, v1)
                # delay from output to input is ~108 ns
                R1.acquire('non-weighed', 'increment', t_offset=160)

            with p.parallel():
                P1.block_pulse(500, v1)
                P2c.block_pulse(500, v1)
                P2.block_pulse(500, v2)
                R1.acquire_weighted('weighed', 'increment', 'gaus100', t_offset=160)

            p.wait(1100)

    p.compile(listing=True, annotate=True)
    return instrument, p


def get_acquired_data(run):
    """Returns non-weighed and weighed data in V."""
    vmax_in = 0.5
    p = run.program
    integration_length = p.R1.integration_length_acq
    data_n = run.get_acquisition_bins('R1', 'non-weighed')
    data_w = run.get_acquisition_bins('R1', 'weighed')
    shape = (p.repetitions, N, N)
    dn0 = np.array(data_n['integration']['path0']).reshape(shape)/integration_length*vmax_in
    dn1 = np.array(data_n['integration']['path1']).reshape(shape)/integration_length*vmax_in
    dw0 = np.array(data_w['integration']['path0']).reshape(shape)*vmax_in
    dw1 = np.array(data_w['integration']['path1']).reshape(shape)*vmax_in
    return dn0, dn1, dw0, dw1


def test_acquire(q1):
    run = q1.run(build_acquire)
    dn0, dn1, dw0, dw1 = get_acquired_data(run.main)
    with np.printoptions(precision=2, threshold=1000):
        print('non-weighed')
        print(dn0)
        print(dn1)
        print('weighed')
        print(dw0)
        print(dw1)


if __name__ == "__main__":
    run_interactive(test_acquire)
