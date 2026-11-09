from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=100e6)
    # add Q on channel 2, I on channel 3
    instrument.add_control('q2', t.qcm.name, [3, 2], nco_frequency=50e6)

    p = instrument.new_program('iq_pulse_1ns')
    p.repetitions = 1

    q1 = p.q1
    q2 = p.q2

    q1.block_pulse(50, 0.5)
    q2.block_pulse(51, 0.4)
    q1.block_pulse(52, 0.5)
    q2.block_pulse(53, 0.4)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_iq_pulse_1ns(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_iq_pulse_1ns)
