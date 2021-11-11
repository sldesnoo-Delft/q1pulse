from .builderbase import Statement
from .register_statements import (
        RegisterAssignment, RegisterAdd
        )

class BranchStatement(Statement):
    def __init__(self, sequence, label):
        self._sequence = sequence
        self._label = label

    @property
    def sequence(self):
        return self._sequence


def _init_reg(generator, register, value):
    RegisterAssignment(register, value, allocate=True).write_instruction(generator)


class RepeatStatement(BranchStatement):
    def __init__(self, sequence, label, loop_register, n):
        super().__init__(sequence, label)
        self._loop_register = loop_register
        self._n = n

    def __repr__(self):
        return f'repeat({self._n}):'

    def write_instruction(self, generator):
        _init_reg(generator, self._loop_register, self._n)
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
        self._loop_stop_register = loop_registers[1]
        self._loop = loop

    def __repr__(self):
        l = self._loop
        return f'loop({l.start}, {l.stop}, {l.step}):{self._loop.loopvar.reg_name}'

    def write_instruction(self, generator):
        l = self._loop
        _init_reg(generator, self._loop_register, l.start)
        if generator.emulate_signed and (l.start < 0 or l.stop < 0):
            generator.add_comment('         --- emulate signed')
            stop = l.stop if l.step > 0 else l.stop + 1
            _init_reg(generator, self._loop_stop_register, stop)
            generator.bits_xor(self._loop_stop_register, 0x8000_0000, self._loop_stop_register)
        generator.set_label(self._label)

class EndLoopStatement(Statement):
    def __init__(self, label, loop_registers, loop):
        self._label = label
        self._loop_register = loop_registers[0]
        self._loop_stop_register = loop_registers[1]
        self._loop = loop

    def __repr__(self):
        return 'endloop'

    def write_instruction(self, generator):
        l = self._loop
        # increment loop register
        incr = RegisterAdd(self._loop_register, self._loop_register, l.step)
        incr.write_instruction(generator)
        # jlt, register,
        if generator.emulate_signed and (l.start < 0 or l.stop < 0):
            with generator.temp_regs(1) as loop_temp:
                generator.add_comment('         --- emulate signed')
                generator.bits_xor(self._loop_register, 0x8000_0000, loop_temp)
                if l.step > 0:
                    generator.jlt(loop_temp, self._loop_stop_register, self._label)
                else:
                    generator.jge(loop_temp, self._loop_stop_register, self._label)
        else:
            if l.step > 0:
                generator.jlt(self._loop_register, l.stop, self._label)
            else:
                generator.jge(self._loop_register, l.stop + 1, self._label)


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
            _init_reg(generator, self._loop_registers[i], value)
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
        incr = RegisterAdd(freg, freg, l.increment)
        incr.write_instruction(generator)
        # loop, register
        generator.loop(loopreg, self._label)


