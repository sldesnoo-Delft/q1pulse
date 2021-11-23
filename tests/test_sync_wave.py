import numpy as np
from pprint import pprint
from q1pulse.instrument import Q1Instrument

from init_pulsars import qcm0, qrm1

instrument = Q1Instrument()
instrument.add_qcm(0, qcm0)
instrument.add_qrm(1, qrm1)
instrument.add_control('P1', 1, [0])
instrument.add_control('P2', 0, [1])

p = instrument.new_program('sync_wave')
p.repetitions = 10_000_000

P1 = p.P1
P2 = p.P2
block = np.concatenate([
        -0.5*np.ones(10),
        -0.5*np.ones(10),
        ])
#block = np.concatenate([
#        np.linspace(0,-0.5, 2, endpoint=False),
#        -0.5*np.ones(6),
#        np.linspace(-0.5, 0.5, 4, endpoint=False),
#        0.5*np.ones(6),
#        np.linspace(0.5, 0, 2, endpoint=False),
#        ])
P1.add_wave('block', block)
P2.add_wave('block', block)

P1.set_gain(1.0)
P2.set_gain(1.0)
p.wait(4)
with p.loop_range(2):
    with p.parallel():
        P1.play('block')
        P2.play('block')
        p.wait(20)

p.wait(10000)
p.describe()

p.compile(listing=True)

instrument.run_program(p)
