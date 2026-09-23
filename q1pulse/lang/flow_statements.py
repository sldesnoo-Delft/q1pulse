from abc import abstractmethod
from .sequence import BlockStatement


class LoopDurationStatement:  # TODO add to end loop?
    ''' Adds loop duration for compiler. Does not add a statement. '''

    def __init__(self, n, t_loop):
        self.n = n
        self.t_loop = t_loop

    def __repr__(self):
        return f'    --- loop duration: {self.n*self.t_loop}'

    def write_instruction(self, generator):
        generator.adjust_time((self.n-1) * self.t_loop)


def _assign_reg(generator, register, value, allocate=True):
    if allocate:
        generator.allocate_reg(register.name)
    generator.move(value, register)


def _increment_reg(generator, register, incr):
    generator.add(register, incr, register)


class LoopBlockBase(BlockStatement):

    # TODO: start/end can shift to match 4 ns constraint. First statement after loop must also be known!!

    def __init__(self, time, loop):
        super().__init__(time)
        self._loop = loop

    def __repr__(self):
        return repr(self._loop) + f" t={self.t_block_start}"

    @abstractmethod
    def write_loop_init(self, generator):
        ...

    @abstractmethod
    def write_loop_end(self, generator):
        ...

    def write_instruction(self, generator):
        with generator.scope():
            # Note: even without timed statements the waits must be looped.
            if self.has_timed_statements or (self.t_block_start != self.t_block_end):
                generator.rt_seq_end(self.t_block_start)

                self.write_loop_init(generator)
                # only 1 branch...
                for branch in self.branches:
                    generator.rt_seq_start(self.t_block_start)
                    branch.compile(generator)
                    generator.rt_seq_end(self.t_block_end)
                generator.add_comment(f"endloop t={self.t_block_end}")
                self.write_loop_end(generator)
                generator.rt_seq_start(self.t_block_end)
            else:
                # A loop without timed statements occurs at other (parallel) sequencers.
                # It could also occur in computations, but would be really rare.

                self.write_loop_init(generator)
                # only 1 branch...
                for branch in self.branches:
                    branch.compile(generator)
                self.write_loop_end(generator)


class LoopBlock(LoopBlockBase):

    def write_loop_init(self, generator):
        loop = self._loop
        if loop.loopvar:
            _assign_reg(generator, loop.loopvar, loop.start)
        _assign_reg(generator, loop._loop_reg, loop._n)
        generator.set_label(loop.label)

    def write_loop_end(self, generator):
        loop = self._loop
        if loop.loopvar:
            # increment loop value
            _increment_reg(generator, loop.loopvar, loop.step)
        # loop, register
        generator.loop(loop._loop_reg, '@'+loop.label)


class ArrayLoopBlock(LoopBlockBase):

    def write_loop_init(self, generator):
        loop = self._loop
        loop = self._loop

        # set data address register to data_label
        _assign_reg(generator, loop._data_ptr, '@'+loop._table_label)
        # set first value
        _assign_reg(generator, loop.loopvar, loop.values[0])
        # decrement data pointer with 2, because first value already loaded
        _increment_reg(generator, loop._data_ptr, -2)
        # start loop
        generator.set_label(loop.label)
        # increment data pointer with 2 for next value
        _increment_reg(generator, loop._data_ptr, 2)

    def write_loop_end(self, generator):
        loop = self._loop
        # jump to data address
        generator.jmp(loop._data_ptr)
        # set data start label
        generator.set_label(loop._table_label)
        for value in loop.values[1:]:
            # set next value
            _assign_reg(generator, loop.loopvar, value, allocate=False)
            # jump to loop start
            generator.jmp('@'+loop.label)
        # NOTE: last jump will end here at the end of loop.
