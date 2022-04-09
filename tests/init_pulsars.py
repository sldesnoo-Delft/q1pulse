import qcodes as qc

try:
    from pulsar_qcm.pulsar_qcm import pulsar_qcm, pulsar_qcm_dummy
    from pulsar_qrm.pulsar_qrm import pulsar_qrm, pulsar_qrm_dummy
    _legacy_pulsar = True
except:
    from qblox_instruments import Pulsar
    _legacy_pulsar = False

try:
    from q1simulator import Q1Simulator
    _q1simulator_found = True
except:
    print('package q1simulator not found')
    _q1simulator_found = False


if _legacy_pulsar:
    def add_module(module_type, name, ip_addr):
        try:
            pulsar = station[name]
        except:
            if _use_simulator:
                if not _q1simulator_found:
                    raise Exception('q1simulator not found')
                pulsar = Q1Simulator(name, sim_type=module_type)
            elif module_type == 'QRM':
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

else:
    def add_module(module_type, name, ip_addr):
        try:
            pulsar = station[name]
        except:
            if _use_simulator:
                if not _q1simulator_found:
                    raise Exception('q1simulator not found')
                pulsar = Q1Simulator(name, sim_type=module_type)
            elif _use_dummy:
                print(f'Starting {module_type} {name} dummy')
                pulsar = Pulsar(name, ip_addr, dummy_type='Pulsar '+module_type)
                pulsar.is_dummy = True
            else:
                print(f'Connecting {module_type} {name} on {ip_addr}...')
                pulsar = Pulsar(name, ip_addr)

            station.add_component(pulsar)

        pulsar.reset()
        return pulsar

if not qc.Station.default:
    station = qc.Station()
else:
    station = qc.Station.default

_use_simulator = True
_use_dummy = True

qcm0 = add_module('QCM', 'qcm0', '192.168.0.2')
qrm1 = add_module('QRM', 'qrm1', '192.168.0.3')

qcm0.reference_source('internal')
qrm1.reference_source('external')
