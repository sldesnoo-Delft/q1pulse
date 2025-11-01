
from qblox_instruments import __version__ as qblox_version_str
from packaging.version import Version
from q1pulse import __version__ as q1pulse_version


def check_qblox_instrument_version():
    min_version = "0.14.0"
    max_version = "1.0.0"
    if qblox_version < Version(min_version):
        raise Exception(f'Q1Pulse {q1pulse_version} requires qblox_instruments {min_version}+')
    if qblox_version > Version(max_version):
        print(f'WARNING Q1Pulse {q1pulse_version} has not been tested on qblox_instruments {qblox_version}')


qblox_version = Version(qblox_version_str)
