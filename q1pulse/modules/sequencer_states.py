from dataclasses import dataclass, field
from logging import DEBUG, INFO, WARNING, ERROR
import logging

logger = logging.getLogger(__name__)

_flag_map = {
    'DISARMED': ERROR,
    'FORCED STOP': ERROR,
    'SEQUENCE PROCESSOR Q1 ILLEGAL INSTRUCTION': ERROR,
    'SEQUENCE PROCESSOR RT EXEC ILLEGAL INSTRUCTION': ERROR,
    'SEQUENCE PROCESSOR RT EXEC COMMAND UNDERFLOW': ERROR,
    'AWG WAVE PLAYBACK INDEX INVALID PATH 0': ERROR,
    'AWG WAVE PLAYBACK INDEX INVALID PATH 1': ERROR,
    'ACQ WEIGHT PLAYBACK INDEX INVALID PATH 0': ERROR,
    'ACQ WEIGHT PLAYBACK INDEX INVALID PATH 1': ERROR,
    'ACQ SCOPE DONE PATH 0': DEBUG,
    'ACQ SCOPE DONE PATH 1': DEBUG,
    'ACQ SCOPE OUT OF RANGE PATH 0': WARNING,
    'ACQ SCOPE OUT OF RANGE PATH 1': WARNING,
    'ACQ SCOPE OVERWRITTEN PATH 0': INFO,
    'ACQ SCOPE OVERWRITTEN PATH 1': INFO,
    'ACQ BINNING DONE': DEBUG,
    'ACQ BINNING FIFO ERROR': ERROR,
    'ACQ BINNING COMM ERROR': ERROR,
    'ACQ BINNING OUT OF RANGE': WARNING,
    'ACQ INDEX INVALID': ERROR,
    'ACQ BIN INDEX INVALID': ERROR,
    'TRIGGER NETWORK CONFLICT': ERROR,
    'TRIGGER NETWORK MISSED INTERNAL TRIGGER': ERROR,
    'OUTPUT OVERFLOW': ERROR,
    'CLOCK INSTABILITY': ERROR,
    'ACQ INTEGRATOR OUT OF RANGE PATH 0': WARNING,
    'ACQ INTEGRATOR OUT OF RANGE PATH 1': WARNING,
    }


@dataclass
class SequencerStatus:
    state: str
    # field status added in qblox version 0.12
    status: str = 'OKAY'
    level: int = 10
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info_msgs: list[str] = field(default_factory=list)
    debug_msgs: list[str] = field(default_factory=list)
    input_overloaded: bool = False

    def __post_init__(self):
        self.msg_list = {
            ERROR: self.errors,
            WARNING: self.warnings,
            INFO: self.info_msgs,
            DEBUG: self.debug_msgs,
            }

    def __str__(self):
        result = f'status:{self.status}, state:{self.state}'
        if len(self.errors):
            result += f', errors:{self.errors}'
        if len(self.warnings):
            result += f', warnings:{self.warnings}'
        if len(self.info_msgs+self.debug_msgs):
            result += f', info:{self.info_msgs+self.debug_msgs}'
        return result

    def add_flags(self, flags):
        for flag in flags:
            flag_str = str(flag).replace('_', ' ')
            if flag_str not in _flag_map:
                logger.error(f'Unknown flag {flag_str} in sequencer state')
                self.errors.append(flag_str)
                self.level = ERROR
            else:
                level = _flag_map[flag_str]
                if 'OUT OF RANGE' in flag_str:
                    self.input_overloaded = True
                self.level = max(level, self.level)
                self.msg_list[level].append(flag_str)


def translate_seq_status(seq_status):
    status = SequencerStatus(seq_status.state, seq_status.status)
    status.add_flags(seq_status.info_flags)
    status.add_flags(seq_status.warn_flags)
    status.add_flags(seq_status.err_flags)

    return status
