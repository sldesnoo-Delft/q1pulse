from .base import Statement
from .register import Register
from .timed_statements import TimedStatement


class FeedbackEventID:
    """A (global) feedback event id.
    Event ID is generated during compilation.
    """
    def __init__(self, name: str, event_id: int):
        self.name = name
        self.event_id = event_id

    def __repr__(self):
        return f"event: {self.name}, id: {self.event_id}"

    def __eq__(self, lhs):
        return isinstance(lhs, FeedbackEventID) and lhs.event_id == self.event_id

    def __hash__(self):
        return self.event_id


class FeedbackPopData(Statement):
    def __init__(self, fb_id: FeedbackEventID, register: Register):
        self.fb_id = fb_id
        self.register = register

    def __repr__(self):
        return f"fb_pop_data {self.fb_id},{self.register}"

    def write_instruction(self, generator):
        generator.fb_pop_data(self.fb_id.event_id, self.register)


class FeedbackPullData(Statement):
    def __init__(self, event_id_dest: Register, register: Register):
        self.event_id_dest = event_id_dest
        self.register = register

    def __repr__(self):
        return f"fb_pull_data {self.event_id_dest},{self.register}"

    def write_instruction(self, generator):
        generator.fb_pull_data(self.event_id_dest, self.register)


class FeedbackSendData(TimedStatement):
    def __init__(self, time: int, fb_id: FeedbackEventID, register: Register):
        super().__init__(time)
        self.fb_id = fb_id
        self.register = register

    def __repr__(self):
        return f"fb_com_data {self.fb_id},{self.register}"

    def write_instruction(self, generator):
        generator.fb_com_data(self.time, self.fb_id.event_id, self.register)


class FeedbackComCfg(TimedStatement):
    def __init__(self, time: int, write_combine: bool, shift: int, n_bytes: int):
        super().__init__(time)
        self.write_combine = int(write_combine)
        self.shift = shift
        self.n_bytes = n_bytes

    def __repr__(self):
        return f"fb_com_cfg {self.write_combine},{self.shift},{self.n_bytes}"

    def write_instruction(self, generator):
        generator.fb_com_cfg(self.time, self.write_combine, self.shift, self.n_bytes)


class FeedbackComExtra(TimedStatement):
    def __init__(self, time: int, valid: bool, value: int):
        super().__init__(time)
        self.valid = int(valid)
        self.value = value

    def __repr__(self):
        return f"fb_com_extra {self.valid},{self.value}"

    def write_instruction(self, generator):
        generator.fb_com_extra(self.time, self.valid, self.value)


# --- Acquisition ---

class FeedbackAcqIqId(TimedStatement):
    def __init__(self, time: int, fb_id: FeedbackEventID):
        super().__init__(time)
        self.fb_id = fb_id

    def __repr__(self):
        return f"fb_acq_iq_id {self.fb_id}"

    def write_instruction(self, generator):
        generator.fb_acq_iq_id(self.time, self.fb_id.event_id)


class FeedbackAcqIqShift(TimedStatement):
    def __init__(self, time: int, rshift: int):
        super().__init__(time)
        self.rshift = rshift

    def __repr__(self):
        return f"fb_acq_iq_shift {self.rshift}"

    def write_instruction(self, generator):
        generator.fb_acq_iq_shift(self.time, self.rshift)


class FeedbackAcqTbId(TimedStatement):
    def __init__(self, time: int, fb_id: FeedbackEventID):
        super().__init__(time)
        self.fb_id = fb_id

    def __repr__(self):
        return f"fb_acq_tb_id {self.fb_id}"

    def write_instruction(self, generator):
        generator.fb_acq_tb_id(self.time, self.fb_id.event_id)


class FeedbackAcqTbCfg(TimedStatement):
    def __init__(self, time: int, write_combine: bool, shift: int, n_bytes: int):
        super().__init__(time)
        self.write_combine = int(write_combine)
        self.shift = shift
        self.n_bytes = n_bytes

    def __repr__(self):
        return f"fb_acq_tb_cfg {self.write_combine},{self.shift},{self.n_bytes}"

    def write_instruction(self, generator):
        generator.fb_acq_tb_cfg(self.time, self.write_combine, self.shift, self.n_bytes)


class FeedbackAcqTbExtra(TimedStatement):
    def __init__(self, time: int, valid: bool, value: int):
        super().__init__(time)
        self.valid = int(valid)
        self.value = value

    def __repr__(self):
        return f"fb_acq_tb_extra {self.valid},{self.value}"

    def write_instruction(self, generator):
        generator.fb_acq_tb_extra(self.time, self.valid, self.value)


class FeedbackAcqTbValid(TimedStatement):
    def __init__(self, time: int, valid: bool):
        super().__init__(time)
        self.valid = int(valid)

    def __repr__(self):
        return f"fb_acq_tb_valid {self.valid}"

    def write_instruction(self, generator):
        generator.fb_acq_tb_valid(self.time, self.valid)


class FeedbackAcqTbMock(TimedStatement):
    def __init__(self, time: int, enable: bool, valid: bool, data: int):
        super().__init__(time)
        self.enable = int(enable)
        self.valid = int(valid)
        self.data = data

    def __repr__(self):
        return f"fb_acq_tb_mock {self.enable},{self.valid},{self.data}"

    def write_instruction(self, generator):
        generator.fb_acq_tb_mock(self.time, self.enable, self.valid, self.data)
