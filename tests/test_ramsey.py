from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_qrm(t.qrm)
    instrument.add_control('q1', t.qcm.name, [0, 1], nco_frequency=50e6)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])
    instrument.add_readout('R1', t.qrm.name, [1])

    p = instrument.new_program('ramsey')
    p.repetitions = 2

    q1 = p.q1
    R1 = p['R1']

    R1.add_acquisition_bins('q1value', 20)

    gates = ['P1', 'P2']
    v_init = [0.120, 0.040]
    v_manip = [0.0, 0.0]
    v_read = [-0.030, 0.060]

    t_pulse = 80
    v_pulse = 0.5

    R1.reset_bin_counter('q1value')
    with p.loop_range(100, 2001, 100) as t_wait:
        p.block_pulse(200, gates, v_init)
        p.ramp(20, gates, v_init, v_manip)
        q1.block_pulse(t_pulse, v_pulse)
        p.wait(t_wait)
        q1.block_pulse(t_pulse, v_pulse)
        p.ramp(100, gates, v_manip, v_read)
        with p.parallel():
            p.set_offsets(gates, v_read)
            p.wait(1000)
            R1.acquire('q1value', 'increment', t_offset=100)
        p.set_offsets(gates, [0.0, 0.0])

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_ramsey(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_ramsey)
