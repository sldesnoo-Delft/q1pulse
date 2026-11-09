from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])
    instrument.add_control('P2', t.qcm.name, [3])

    p = instrument.new_program('bb_1ns_resolution')
    p.repetitions = 3

    P1 = p.P1
    P2 = p.P2

    p.wait(8)
    for i in range(4):
        with p.parallel():
            P1.block_pulse(20, 0.5, t_offset=4)
            P2.block_pulse(20-2*i, 0.5, t_offset=4+i)
        p.wait(4)

    P1.wait(7)
    P1.block_pulse(15, 0.4)
    p.wait(100)
    for i in range(4):
        with p.parallel():
            P2.ramp(11, 0.0, 0.5)
            P2.block_pulse(12, 0.5, t_offset=11)
            P2.ramp(11, 0.5, 0.0, t_offset=23)
            P1.ramp(11, 0.0, 0.5, t_offset=i)
            P1.block_pulse(12-2*i, 0.5, t_offset=11+i)
            P1.ramp(11, 0.5, 0.0, t_offset=23-i)
        p.wait(5)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_1ns_resolution(q1):
    q1.run(build)


if __name__ == "__main__":
    run_interactive(test_1ns_resolution)
