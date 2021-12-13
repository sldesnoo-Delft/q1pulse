from .timed_statements import TimedStatement

class LoopDurationStatement: # @@@ add to end loop?
    ''' Adds loop duration for compiler. Does not add a statement. '''
    def __init__(self, n, t_loop):
        self.n = n
        self.t_loop = t_loop

    def __repr__(self):
        return f'    --- loop duration: {self.n*self.t_loop}'

    def write_instruction(self, generator):
        generator.adjust_time((self.n-1) * self.t_loop)



class BranchStatement(TimedStatement):
    def __init__(self, time, sequence, label):
        super().__init__(time)
        self._sequence = sequence
        self._label = label

    @property
    def sequence(self):
        return self._sequence


def _assign_reg(generator, register, value, allocate=True):
    statement = register.assign(value, allocate=allocate)
    statement.write_instruction(generator)

def _increment_reg(generator, register, incr):
    statement = register.assign(register + incr)
    statement.write_instruction(generator)

class LoopStatement(BranchStatement):
    def __init__(self, time, sequence, loop):
        super().__init__(time, sequence, loop.label)
        self._loop = loop

    def __repr__(self):
        return repr(self._loop)

    def write_instruction(self, generator):
        generator._wait_till(self.time)
        l = self._loop
        if l.loopvar:
            _assign_reg(generator, l.loopvar, l.start)
        _assign_reg(generator, l._loop_reg, l._n)
        generator.set_label(self._label)


class EndLoopStatement(TimedStatement):
    def __init__(self, time, loop):
        super().__init__(time)
        self._label = loop.label
        self._loop = loop

    def __repr__(self):
        return 'endloop'

    def write_instruction(self, generator):
        generator._wait_till(self.time)
        l = self._loop
        if l.loopvar:
            # increment loop value
            _increment_reg(generator, l.loopvar, l.step)
        # loop, register
        generator.loop(l._loop_reg, self._label)


class ArrayLoopStatement(BranchStatement):
    def __init__(self, time, sequence, loop):
        super().__init__(time, sequence, loop.label)
        self._loop = loop

    def __repr__(self):
        return repr(self._loop)

    def write_instruction(self, generator):
        generator._wait_till(self.time)
        l = self._loop

        # set data address register to data_label
        _assign_reg(generator, l._data_ptr, '@' + l._table_label)
        # set first value
        _assign_reg(generator, l.loopvar, l.values[0])
        # decrement data pointer with 2, because first value already loaded
        _increment_reg(generator, l._data_ptr, -2)
        # start loop
        generator.set_label(self._label)
        # increment data pointer with 2 for next value
        _increment_reg(generator, l._data_ptr, 2)

class EndArrayLoopStatement(TimedStatement):
    def __init__(self, time, loop):
        super().__init__(time)
        self._label = loop.label
        self._loop = loop

    def __repr__(self):
        return 'endloop'

    def write_instruction(self, generator):
        generator._wait_till(self.time)
        l = self._loop
        # jump to data address
        generator.jmp(l._data_ptr)
        # set data start label
        generator.set_label(l._table_label)
        for value in l.values[1:]:
            # set next value
            _assign_reg(generator, l.loopvar, value, allocate=False)
            # jump to loop start
            generator.jmp(self._label)
        # NOTE: last jump will end here at the end of loop.
