from .base import Statement

class BranchStatement(Statement):
    def __init__(self, sequence, label):
        self._sequence = sequence
        self._label = label

    @property
    def sequence(self):
        return self._sequence


def _assign_reg(generator, register, value):
    statement = register.assign(value, allocate=True)
    statement.write_instruction(generator)

def _increment_reg(generator, register, incr):
    statement = register.assign(register + incr)
    statement.write_instruction(generator)


class RepeatStatement(BranchStatement):
    def __init__(self, sequence, label, loop):
        super().__init__(sequence, label)
        self._loop = loop

    def __repr__(self):
        return repr(self._loop)

    def write_instruction(self, generator):
        l = self._loop
        _assign_reg(generator, l._loop_reg, l._n)
        generator.set_label(self._label)

class EndRepeatStatement(Statement):
    def __init__(self, label, loop):
        self._label = label
        self._loop = loop

    def __repr__(self):
        return 'endloop'

    def write_instruction(self, generator):
        generator.loop(self._loop._loop_reg, self._label)


class LoopStatement(BranchStatement):
    def __init__(self, sequence, label, loop):
        super().__init__(sequence, label)
        self._loop = loop

    def __repr__(self):
        return repr(self._loop)

    def write_instruction(self, generator):
        l = self._loop
        _assign_reg(generator, l.loopvar, l.start)
        _assign_reg(generator, l._loop_reg, l._n)
        generator.set_label(self._label)


class EndLoopStatement(Statement):
    def __init__(self, label, loop):
        self._label = label
        self._loop = loop

    def __repr__(self):
        return 'endloop'

    def write_instruction(self, generator):
        l = self._loop
        # increment loop register
        _increment_reg(generator, l.loopvar, l.step)
        # loop, register
        generator.loop(l._loop_reg, self._label)


class LinspaceLoopStatement(BranchStatement):
    def __init__(self, sequence, label, loop):
        super().__init__(sequence, label)
        self._loop = loop

    def __repr__(self):
        return repr(self._loop)

    def write_instruction(self, generator):
        l = self._loop
        _assign_reg(generator, l.loopvar, l.start)
        _assign_reg(generator, l._loop_reg, l.n)
        generator.set_label(self._label)

class EndLinspaceLoopStatement(Statement):
    def __init__(self, label, loop):
        self._label = label
        self._loop = loop

    def __repr__(self):
        return 'endloop'

    def write_instruction(self, generator):
        l = self._loop
        _increment_reg(generator, l.loopvar, l.increment)
        # loop, register
        generator.loop(l._loop_reg, self._label)


