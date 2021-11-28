import qcodes as qc

from pulsar_qcm.pulsar_qcm import pulsar_qcm, pulsar_qcm_dummy
from pulsar_qrm.pulsar_qrm import pulsar_qrm, pulsar_qrm_dummy

if not qc.Station.default:
    station = qc.Station()
else:
    station = qc.Station.default

_use_dummy=True

def add_module(module_type, module_nr, ip_addr):
    name = f'{module_type}_{module_nr}'
    try:
        pulsar = station[name]
    except:
        if module_type == 'qrm':
            if _use_dummy:
                print(f'Starting QRM qrm_{module_nr} dummy')
                pulsar = pulsar_qrm_dummy(name)
            else:
                print(f'Connecting QRM {module_nr} on {ip_addr}...')
                pulsar = pulsar_qrm(name, ip_addr)
        else:
            if _use_dummy:
                print(f'Starting QCM qcm_{module_nr} dummy')
                pulsar = pulsar_qcm_dummy(name)
            else:
                print(f'Connecting QCM {module_nr} on {ip_addr}...')
                pulsar = pulsar_qcm(name, ip_addr)

        pulsar.reset()
        station.add_component(pulsar)

    return pulsar

qcm0 = add_module('qcm', 0, '192.168.0.2')
qrm1 = add_module('qrm', 1, '192.168.0.3')

# TODO @@@ move to instrument
qcm0.reference_source('internal')
qrm1.reference_source('external')
