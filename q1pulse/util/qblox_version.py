
from qblox_instruments import __version__ as qblox_version_str
from packaging.version import Version

def check_qblox_instrument_version():
    if qblox_version >= Version('0.8'):
        print(f'WARNING Q1Pulse has not yet been tested on qblox_instruments version {qblox_version}')
    elif qblox_version < Version('0.7'):
        print('WARNING: Update qblox_instruments and firmware to v0.7.x for best performance.')
    elif qblox_version < Version('0.6'):
        raise Exception('Q1Pulse requires qblox_instruments version >= 0.6.0')

qblox_version = Version(qblox_version_str)
