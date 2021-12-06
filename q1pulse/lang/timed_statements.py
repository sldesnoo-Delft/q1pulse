from .base import Statement

class TimedStatement(Statement):
    def __init__(self, time):
        self.time = time

class SyncTimeStatement(TimedStatement):
    def __init__(self, time):
        super().__init__(time)

    def __repr__(self):
        return f'sync_seq'

    def write_instruction(self, generator):
        generator._schedule_update(self.time)

class LoopDurationStatement:
    ''' Adds loop duration for compiler. Does not add a statement. '''
    def __init__(self, n, t_loop):
        self.n = n
        self.t_loop = t_loop

    def __repr__(self):
        return f'    --- loop duration: {self.n*self.t_loop}'

    def write_instruction(self, generator):
        generator.adjust_time((self.n-1) * self.t_loop)


class WaitRegStatement(TimedStatement):
    def __init__(self, time, register):
        super().__init__(time)
        self.register = register

    def __repr__(self):
        return f'wait({self.register})'

    def write_instruction(self, generator):
        generator.wait_reg(self.time, self.register)


class SetMarkersStatement(TimedStatement):
    def __init__(self, time, value):
        super().__init__(time)
        self.value = value

    def __repr__(self):
        return f'set_mrk 0b{self.value:04b}'

    def write_instruction(self, generator):
        generator.set_mrk(self.time, self.value)


class PlayWaveStatement(TimedStatement):
    def __init__(self, time, wave0, wave1):
        super().__init__(time)
        self.wave0 = wave0
        self.wave1 = wave1

    def __repr__(self):
        wave0 = self.wave0.name if self.wave0 is not None else None
        wave1 = self.wave1.name if self.wave1 is not None else None
        return f'play {wave0} {wave1}'

    def write_instruction(self, generator):
        generator.play(self.time, self.wave0, self.wave1)

class ShiftPhaseStatement(TimedStatement):
    def __init__(self, time, delta, hires_regs=False):
        super().__init__(time)
        self.delta = delta
        self.hires_regs = hires_regs

    def __repr__(self):
        return f'phase_delta {self.delta}'

    def write_instruction(self, generator):
        generator.add_phase(self.time, self.delta, self.hires_regs)

class SetPhaseStatement(TimedStatement):
    def __init__(self, time, delta, hires_regs=False):
        super().__init__(time)
        self.delta = delta
        self.hires_regs = hires_regs

    def __repr__(self):
        return f'set_phase {self.delta}'

    def write_instruction(self, generator):
        generator.set_phase(self.time, self.delta, self.hires_regs)

class AwgDcOffsetStatement(TimedStatement):
    def __init__(self, time, offset0, offset1):
        super().__init__(time)
        self.offset0 = offset0
        self.offset1 = offset1

    def __repr__(self):
        return f'awg_offset = {self.offset0}, {self.offset1}'

    def write_instruction(self, generator):
        generator.awg_offset(self.time, self.offset0, self.offset1)


class AwgGainStatement(TimedStatement):
    def __init__(self, time, gain0, gain1):
        super().__init__(time)
        self.gain0 = gain0
        self.gain1 = gain1

    def __repr__(self):
        return f'awg_gain = {self.gain0}, {self.gain1}'

    def write_instruction(self, generator):
        generator.awg_gain(self.time, self.gain0, self.gain1)

class AcquireStatement(TimedStatement):
    def __init__(self, time, bins, bin_index):
        super().__init__(time)
        self.bins = bins
        self.bin_index = bin_index

    def __repr__(self):
        return f'acquire(bins={self.bins.name}, bin={self.bin_index})'

    def write_instruction(self, generator):
        generator.acquire(self.time, self.bins, self.bin_index)

class AcquireWeighedStatement(TimedStatement):
    def __init__(self, time, bins, bin_index, weight0, weight1):
        super().__init__(time)
        self.bins = bins
        self.bin_index = bin_index
        self.weight0 = weight0
        self.weight1 = weight1

    def __repr__(self):
        weight0 = self.weight0.name if self.weight0 is not None else None
        weight1 = self.weight1.name if self.weight1 is not None else None
        return (
            f'acquire_weighed(bins={self.bins.name}, bin={self.bin_index}, '+
            f'weight0={weight0}, weight1={weight1})')

    def write_instruction(self, generator):
        generator.acquire_weighed(self.time, self.bins, self.bin_index,
                                  self.weight0, self.weight1)