import qcodes as qc

from qblox_instruments import Pulsar
from qblox_instruments import Cluster, ClusterType, PlugAndPlay
#from pprint import pprint

try:
    from q1simulator import Q1Simulator
    _q1simulator_found = True
except:
    print('package q1simulator not found')
    _q1simulator_found = False


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
            # set property is_dummy to use in Q1Pulse state checking
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
_use_dummy = False
_use_cluster = False

with PlugAndPlay() as p:
    p.print_devices()
#    pprint(p.list_devices())

if _use_cluster:
    try:
        cluster = station['Qblox_Cluster']
        cluster.reset()
        qcm0 = cluster.module8
        qrm1 = cluster.module10
    except:
        dummy_cfg = None
        if _use_dummy:
            cfg = {
                8:ClusterType.CLUSTER_QCM,
                10:ClusterType.CLUSTER_QRM
                }
            cluster = Cluster('Qblox_Cluster', '192.168.0.2', dummy_cfg=cfg)
            # set property is_dummy to use in Q1Pulse state checking
            cluster.is_dummy = True
        else:
            cluster = Cluster('Qblox_Cluster', '192.168.0.2')

        station.add_component(cluster)
        cluster.reset()

        print(f'Cluster:')
        print(cluster.get_system_state())
        for module in cluster.modules:
            if module.present():
                rf = '-RF' if module.is_rf_type else ''
                print(f'  slot {module.slot_idx}: {module.module_type}{rf}')

        qcm0 = cluster.module8
        qrm1 = cluster.module10
        station.add_component(qcm0)
        station.add_component(qrm1)
else:
    qcm0 = add_module('QCM', 'qcm0', '192.168.0.2')
    qrm1 = add_module('QRM', 'qrm1', '192.168.0.3')

    qcm0.reference_source('internal')
    qrm1.reference_source('external')
