from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('P1', t.qcm.name, [0])
    instrument.add_readout('R1', t.qrm.name, [], in_channels=[0])

    # gain = 0: +/- 0.5V; gain -6 dB: +/- 1.0 V
    t.qrm.in0_gain(0)
    t.qrm.in1_gain(0)

    p = instrument.new_program('acquire_ttl')
    p.repetitions = 6

    P1 = p.P1
    R1 = p.R1

    N = 5
    n_acq = max(N, p.repetitions)
    R1.add_acquisition_bins('ttl', n_acq*N)
    R1.ttl_acq_input_select = 0
    R1.ttl_acq_auto_bin_incr_en = False
    R1.ttl_acq_threshold = 0.20 / 0.5  # Threshold at 220 mV

    # output range QCM (P1): +/- 2.5 V
    # input range QRM (R1): +/- 0.5 V (gain = 0 dB)

    v1_max = 0.2/2.5  # 200 mV
    v2_max = 0.2/2.5  # 200 mV

    bin_index = 0 if R1.ttl_acq_auto_bin_incr_en else "increment"

    # Generate 5 pulses per acquisition.
    # Amplitude of first pulse  of sequence increments from 0 to 200 mV.
    # The pulses in the pulse train increment with steps of 50 mV from 0 to 200 mV
    # First acquisition no pulse above threshold.
    # Every iteration over v1 there is one more pulse above threshold.
    with p.loop_linspace(0, v1_max, N) as v1:

        R1.acquire_ttl("ttl", bin_index, 1, t_offset=160)
        p.wait(10)

        with p.loop_linspace(0, v2_max, N) as v2:
            P1.block_pulse(500, v1+v2)
            p.wait(500)

        R1.acquire_ttl("ttl", 0, 0, t_offset=160)

        p.wait(2000)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_acquire_ttl(q1):
    run = q1.run(build)
    data_ttl = run.main.get_acquisition_bins('R1', 'ttl')
    print(data_ttl['avg_cnt'])


if __name__ == "__main__":
    run_interactive(test_acquire_ttl)
