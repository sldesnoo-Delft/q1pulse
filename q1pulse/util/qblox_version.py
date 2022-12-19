
from qblox_instruments import __version__ as qblox_version_str
from packaging.version import Version

def check_qblox_instrument_version():
    if qblox_version >= Version('0.9'):
        print(f'WARNING Q1Pulse has not yet been tested on qblox_instruments version {qblox_version}')
    elif qblox_version < Version('0.8'):
        raise Exception('Q1Pulse v0.8.x requires qblox_instruments version  v0.8.y')

qblox_version = Version(qblox_version_str)
