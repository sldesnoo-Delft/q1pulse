import qcodes as qc

from qblox_instruments import Cluster, ClusterType, PlugAndPlay
#from pprint import pprint

try:
    from q1simulator import Q1Simulator, Cluster as SimCluster
    _q1simulator_found = True
except:
    print('package q1simulator not found')
    _q1simulator_found = False



if not qc.Station.default:
    station = qc.Station()
else:
    station = qc.Station.default

_use_simulator = True
_use_dummy = False

if not _use_simulator and not _use_dummy:
    with PlugAndPlay() as p:
        p.print_devices()
    #    pprint(p.list_devices())


try:
    cluster = station['Qblox_Cluster']
    cluster.reset()
    qcm0 = cluster.module8
    qrm1 = cluster.module10
except:
    if _use_simulator:
        cluster = SimCluster('Qblox_Cluster', {
                8:'QCM',
                10:'QRM',
                })
    elif _use_dummy:
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

    print('Cluster:')
    print(cluster.get_system_status())
    for module in cluster.modules:
        if module.present():
            rf = '-RF' if module.is_rf_type else ''
            print(f'  slot {module.slot_idx}: {module.module_type}{rf}')

    qcm0 = cluster.module8
    qrm1 = cluster.module10
    station.add_component(qcm0)
    station.add_component(qrm1)
