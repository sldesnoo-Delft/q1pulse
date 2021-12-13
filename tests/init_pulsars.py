import qcodes as qc

from pulsar_qcm.pulsar_qcm import pulsar_qcm, pulsar_qcm_dummy
from pulsar_qrm.pulsar_qrm import pulsar_qrm, pulsar_qrm_dummy
try:
    from q1simulator import Q1Simulator
    _q1simulator_found = True
except:
    print('package q1simulator not found')
    _q1simulator_found = False

if not qc.Station.default:
    station = qc.Station()
else:
    station = qc.Station.default

_use_simulator = True
_use_dummy = True

def add_module(module_type, name, ip_addr):
    try:
        pulsar = station[name]
    except:
        if _use_simulator:
            if not _q1simulator_found:
                raise Exception('q1simulator not found')
            pulsar = Q1Simulator(name)
        elif module_type == 'qrm':
            if _use_dummy:
                print(f'Starting QRM {name} dummy')
                pulsar = pulsar_qrm_dummy(name)
            else:
                print(f'Connecting QRM {name} on {ip_addr}...')
                pulsar = pulsar_qrm(name, ip_addr)
        else:
            if _use_dummy:
                print(f'Starting QCM {name} dummy')
                pulsar = pulsar_qcm_dummy(name)
            else:
                print(f'Connecting QCM {name} on {ip_addr}...')
                pulsar = pulsar_qcm(name, ip_addr)

        station.add_component(pulsar)

    pulsar.reset()
    return pulsar

qcm0 = add_module('qcm', 'qcm0', '192.168.0.2')
qrm1 = add_module('qrm', 'qrm1', '192.168.0.3')

qcm0.reference_source('internal')
qrm1.reference_source('external')
