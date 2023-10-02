
from qblox_instruments import __version__ as qblox_version_str
from packaging.version import Version
from q1pulse import __version__ as q1pulse_version

def check_qblox_instrument_version():
    if qblox_version > Version('0.11.1'):
        print(f'WARNING Q1Pulse {q1pulse_version} has not been tested on qblox_instruments version {qblox_version}')
    elif qblox_version < Version('0.9'):
        raise Exception('Q1Pulse {q1pulse_version} requires qblox_instruments version  v0.9+')

qblox_version = Version(qblox_version_str)
