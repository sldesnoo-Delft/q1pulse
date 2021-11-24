from .builderbase import Statement

class BranchStatement(Statement):
    def __init__(self, sequence, label):
        self._sequence = sequence
        self._label = label

    @property
    def sequence(self):
        return self._sequence


def _assign_reg(generator, register, value):
    statement = register.assign(value)
    statement.write_instruction(generator)

def _increment_reg(generator, register, incr):
    statement = register.assign(register + incr)
    statement.write_instruction(generator)


class RepeatStatement(BranchStatement):
    def __init__(self, sequence, label, loop_register, n):
        super().__init__(sequence, label)
        self._loop_register = loop_register
        self._n = n

    def __repr__(self):
        return f'repeat({self._n}):'

    def write_instruction(self, generator):
        _assign_reg(generator, self._loop_register, self._n)
        generator.set_label(self._label)

class EndRepeatStatement(Statement):
    def __init__(self, label, loop_register):
        self._label = label
        self._loop_register = loop_register

    def __repr__(self):
        return 'endloop'

    def write_instruction(self, generator):
        # loop, register
        generator.loop(self._loop_register, self._label)


class LoopStatement(BranchStatement):
    def __init__(self, sequence, label, loop_registers, loop):
        super().__init__(sequence, label)
        self._loop_register = loop_registers[0]
        self._loop_cnt_register = loop_registers[1]
        self._loop = loop

    def __repr__(self):
        l = self._loop
        return f'loop({l.start}, {l.stop}, {l.step}):{self._loop.loopvar.reg_name}'

    def write_instruction(self, generator):
        l = self._loop
        _assign_reg(generator, self._loop_register, l.start)
        _assign_reg(generator, self._loop_cnt_register, l.n)
        generator.set_label(self._label)

class EndLoopStatement(Statement):
    def __init__(self, label, loop_registers, loop):
        self._label = label
        self._loop_register = loop_registers[0]
        self._loop_cnt_register = loop_registers[1]
        self._loop = loop

    def __repr__(self):
        return 'endloop'

    def write_instruction(self, generator):
        l = self._loop
        # increment loop register
        _increment_reg(generator, self._loop_register, l.step)
        # loop, register
        generator.loop(self._loop_cnt_register, self._label)


class LinspaceLoopStatement(BranchStatement):
    def __init__(self, sequence, label, loop_registers, loop):
        super().__init__(sequence, label)
        self._loop_registers = loop_registers
        self._loop = loop

    def __repr__(self):
        l = self._loop
        endpoint = ', endpoint=False' if not l.endpoint else ''
        return f'loop_linspace({l.start}, {l.stop}, {l.n}{endpoint}):{l.loopvar.reg_name}, @{self._label}'

    def write_instruction(self, generator):
        l = self._loop
        for i,value in enumerate([l.n, l.start]):
            _assign_reg(generator, self._loop_registers[i], value)
        generator.set_label(self._label)

class EndLinspaceLoopStatement(Statement):
    def __init__(self, label, loop_registers, loop):
        self._label = label
        self._loop_registers = loop_registers
        self._loop = loop

    def __repr__(self):
        return 'endloop'

    def write_instruction(self, generator):
        l = self._loop
        loopreg, freg = self._loop_registers
        _increment_reg(generator, freg, l.increment)
        # loop, register
        generator.loop(loopreg, self._label)


