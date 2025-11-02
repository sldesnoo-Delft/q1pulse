import json
import logging
from pprint import pprint
from numbers import Number
import numpy as np
import math
from functools import wraps
from contextlib import contextmanager
from dataclasses import dataclass, field

from .generator_data import GeneratorData
from .instruction_queue import InstructionQueue, Instruction, PendingUpdate, MIN_WAIT, CLOCK_PERIOD
from .registers import SequencerRegisters
from ..lang.math_expressions import get_dtype, Expression, Operand
from ..lang.generator import GeneratorBase
from ..lang.register import Register
from ..lang.exceptions import (
        Q1ValueError, Q1TypeError,
        Q1Exception, Q1CompileError
        )

logger = logging.getLogger(__name__)


def _int_u32(value):
    if value < 0:
        return value + (1 << 32)
    return value


def _float_to_f16(value):
    if value < -1.0 or value > 1.0:
        raise Q1ValueError(f'Fixed point value out of range: {value}')
    _f2i16 = (1 << 15) - 0.1
    return math.floor(value * _f2i16)


def _float_to_f32(value):
    if value < -1.0 or value > 1.0:
        raise Q1ValueError(f'Fixed point value out of range: {value}')
    _f2i32 = (1 << 31) - 0.1
    return _int_u32(math.floor(value * _f2i32))


def register_args(signature):
    '''
        Signature:
        I: integer only; Evaluate expression, allow label.
        f: float or int: Evaluate expression, if one float, then all float; label counts as int
        F: float only: Evaluate expression, convert to i16
        t: time. integer, No register. No conversion.
        o: object. No register. No conversion.
    '''
    def arg_I(generator, i, arg, conversion_comments):
        # translate reg, expr. to asm register
        if isinstance(arg, Operand):
            if arg.dtype != int:
                raise Q1TypeError(f'Argument {i} must be of type int ({arg})')
            asm_reg = generator._to_asm_reg(arg)
            if conversion_comments is not None:
                conversion_comments += [f'{arg} -> {asm_reg}']
            return asm_reg
        elif isinstance(arg, str):
            # label or 'Rxx'
            return arg
        else:
            # make unsigned
            return _int_u32(arg)

    def arg_f(generator, i, arg, conversion_comments):
        # Note: label has dtype int

        # dtype = get_dtype(arg)
        # # check optional all float or all int
        # if opt_type is None:
        #     opt_type = dtype
        # elif dtype is not None and dtype != opt_type:
        #     raise Q1TypeError(f'Float/int argument mismatch {dtype}<>{opt_type}')

        if isinstance(arg, str):
            # label or 'Rxx'
            return arg
        elif isinstance(arg, Operand):
            asm_reg = generator._to_asm_reg(arg)
            if conversion_comments is not None:
                conversion_comments += [f'{arg} -> {asm_reg}']
            return asm_reg
        elif get_dtype(arg) == float:
            value = _float_to_f32(arg)
            if conversion_comments is not None:
                conversion_comments += [f'{arg} -> {asm_reg}']
            return value
        else:
            # make unsigned
            return _int_u32(arg)

    def arg_F(generator, i, arg, conversion_comments):
        if arg is None:
            return arg
        elif isinstance(arg, Operand):
            if arg.dtype != float:
                raise Q1TypeError(f'Argument {i} must be of type float ({arg})')
            asm_reg = generator._oper_to_f16(arg)
            if conversion_comments is not None:
                conversion_comments += [f'{arg} -> {asm_reg}']
            return asm_reg
        else:
            value = _float_to_f16(arg)
            if conversion_comments is not None:
                conversion_comments += [f'{arg} -> {value}']
            return value

    arg_conv = []
    for i, atype in enumerate(signature):
        if atype in 'to':
            # argument is time or object. Nothing to translate
            continue
        elif atype == 'I':
            arg_conv.append((i, arg_I))
        elif atype == 'f':
            arg_conv.append((i, arg_f))
        elif atype == 'F':
            arg_conv.append((i, arg_F))

    def decorator_register_args(func):
        @wraps(func)
        def func_wrapper(self, *args, **kwargs):
            try:
                # print(f'{func.__name__} {args}')
                args = list(args)
                self._registers.enter_scope()

                conversion_comments = [] if self._show_arg_conversions else None
                for i, conv_func in arg_conv:
                    arg = args[i]
                    args[i] = conv_func(self, i, arg, conversion_comments)

                if self._show_arg_conversions and len(conversion_comments) > 0:
                    self.add_comment(' -- args: ' + ', '.join(conversion_comments))
                res = func(self, *args, **kwargs)
                self._registers.exit_scope()
                return res
            except Q1Exception as ex:
                msg = f'in call\n    {func.__name__}({",".join(str(arg) for arg in args)})'
                raise Q1CompileError(msg) from ex

        return func_wrapper

    return decorator_register_args


@dataclass
class ConditionalBlockState:
    rt_time_start: int = 0
    n_rt_instruction_start: int = 0
    last_rt_instructions: list[Instruction] = field(default_factory=list)
    rt_end_times: list[int] = field(default_factory=list)


@dataclass
class LastRtSettings:
    awg_offs_time: int = -1
    awg_offs_instr: Instruction = None
    awg_gain_time: int = -1
    awg_gain_instr: Instruction = None

    def clear(self):
        self.awg_gain_time = -1
        self.awg_offs_time = -1


class Q1asmGenerator(InstructionQueue, GeneratorBase):
    def __init__(self, add_comments=False, list_registers=True,
                 line_numbers=True, comment_arg_conversions=False,
                 optimize=1):
        super().__init__(add_comments=add_comments)
        self._list_registers = list_registers
        self._line_numbers = line_numbers
        self._show_arg_conversions = comment_arg_conversions
        self._optimize = optimize
        self.q1asm = None
        self._repetitions = 1
        self._last_rt_settings = LastRtSettings()
        self._conditional_block_state = None
        self._data = GeneratorData()
        self._registers = SequencerRegisters(self._add_reg_comment if add_comments else None)
        # counter for signed ASR emulation
        self._asr_jumps = 0
        self.modifies_frequency = False
        self.add_comment('--INIT--', init_section=True)
        self._zero_reg = self.allocate_reg('_zero')
        self.move(0, self._zero_reg, init_section=True)

    @property
    def repetitions(self):
        return self._repetitions

    @repetitions.setter
    def repetitions(self, value):
        self._repetitions = value

    def start_main(self):
        self._add_rt_command('wait_sync', time=0)
        self._wait_till(100)
        self._reset_time()
        self.add_comment('--START-- (t=0)')
        self.set_label('_start')
        self.block_start()
        self.reset_phase(0) # TODO only if NCO enabled?
        self._contains_io_instr = False

        if self._repetitions > 1:
            self.repetitions_reg = self.allocate_reg('_repetitions')
            self.move(self._repetitions, self.repetitions_reg,
                      init_section=True)

    def end_main(self, time):
        self._wait_till(time)
        self.block_end()
        self.add_comment('--END--')
        if self._repetitions > 1:
            self.loop(self.repetitions_reg, '@_start')
            # Last start/stop to ensure that pending update is set at end of program
            self.block_start()
            self.block_end()
        self._flush_pending_update()
        self._add_instruction('stop')

    def block_start(self):
        # Pending updates of the previous block must be updated now.
        # So, updates scheduled at the end of the loop will be updated
        # at the start of the loop or immediately after the loop.
        self._schedule_update(self._rt_time)
        # rt_settings may not be overwritten across block boundary
        self._last_rt_settings.clear()

    def block_end(self):
        # NOTE pending update will move to next block start.
        self._last_rt_settings.clear()

    def enter_conditional(self, time):
        self._flush_pending_update()
        self._wait_till(time)
        self.add_comment('Start conditional block')
        self._conditional_block_state = ConditionalBlockState()

    def set_condition(self, mask, operator):
        # always use 4 ns for else-wait.
        self._add_instruction('set_cond', 1, mask, operator, MIN_WAIT)
        # Store rt state at start to set the time after the block.
        self._conditional_block_state.n_rt_instruction_start = self._n_rt_instructions
        self._conditional_block_state.rt_time_start = self._rt_time

    def exit_condition(self):
        self._flush_pending_update()
        self._last_rt_settings.clear()
        cbs = self._conditional_block_state
        # add wait command if there is no pending rt command with wait_after time
        if self._last_rt_command is None:
            self._add_rt_command('wait', time=self._rt_time)
        else_time = CLOCK_PERIOD*(self._n_rt_instructions - cbs.n_rt_instruction_start)
        self.add_comment(f'End condition. total wait_else {else_time} ns (t_end={self._rt_time})')
        # update end times of previous branches with time spent in else-wait.
        for i in range(len(cbs.rt_end_times)):
            cbs.rt_end_times[i] += else_time
        # store last rt-statement
        cbs.last_rt_instructions.append(self._last_rt_command)
        cbs.rt_end_times.append(self._rt_time)

        # set time to else time.
        self._rt_time = cbs.rt_time_start + else_time
        self._last_rt_command = None

    def exit_conditional(self, time):
        cbs = self._conditional_block_state
        max_rt_time_branches = max(cbs.rt_end_times)
        if max_rt_time_branches > time:
            self.add_comment(f'End conditional block t={time}, '
                             f'wait_after {max_rt_time_branches-time} ns, '
                             f'next at {max_rt_time_branches} ns')
            time = max_rt_time_branches
        else:
            self.add_comment(f'End conditional block t={time}')
        # update wait after of last instructions
        for rt_instr, end_time in zip(cbs.last_rt_instructions, cbs.rt_end_times):
            rt_instr.wait_after += time-end_time
        # disable condition
        self._add_instruction('set_cond', 0, 0, 0, 4)
        self._conditional_block_state = None
        self._last_rt_command = None
        self._rt_time = time

    @register_args(signature='I')
    def jmp(self, label):
        self._add_instruction('jmp', label)

    @register_args(signature='ffI')
    def jlt(self, register, value, label):
        self._add_instruction('jlt', register, value, label)

    @register_args(signature='ffI')
    def jge(self, register, value, label):
        self._add_instruction('jge', register, value, label)

    @register_args(signature='II')
    def loop(self, register, label):
        self._add_instruction('loop', register, label)

    @register_args(signature='ff')
    def move(self, source, destination, init_section=False):
        self._add_reg_instruction('move', source, destination,
                                  init_section=init_section)

    @register_args(signature='fff')
    def add(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs, rhs = rhs, lhs
        self._add_reg_instruction('add', lhs, rhs, destination)

    @register_args(signature='fff')
    def sub(self, lhs, rhs, destination):
        # q1asm has no instruction for sub imm,reg,reg. Use sub reg,reg,reg instead
        if isinstance(lhs, Number):
            with self._registers.temp_regs(1) as temp:
                self.move(lhs, temp)
                self._add_reg_instruction('sub', temp, rhs, destination)
        else:
            self._add_reg_instruction('sub', lhs, rhs, destination)

    @register_args(signature='fIf')
    def asl(self, lhs, rhs, destination):
        # q1asm has no instruction for asl imm,reg,reg. Use asl reg,reg,reg instead
        if isinstance(lhs, Number):
            with self._registers.temp_regs(1) as temp:
                self.move(lhs, temp)
                self._add_reg_instruction('asl', temp, rhs, destination)
        else:
            self._add_reg_instruction('asl', lhs, rhs, destination)

    @register_args(signature='fIf')
    def lsr(self, lhs, rhs, destination):
        # NOTE: q1asm asr is unsigned, so actually it is an logical shift right
        if isinstance(lhs, Number):
            # q1asm has no instruction for asr imm,reg,reg. Use asr reg,reg,reg instead
            with self._registers.temp_regs(1) as temp:
                self.move(lhs, temp)
                self._add_reg_instruction('asr', temp, rhs, destination)
        else:
            self._add_reg_instruction('asr', lhs, rhs, destination)

    @register_args(signature='fIf')
    def asr(self, lhs, rhs, destination):
        with self.scope():
            if isinstance(lhs, Number):
                # q1asm has no instruction for asr imm,reg,reg. Use asr reg,reg,reg instead
                temp = self.get_temp_reg()
                self.move(lhs, temp)
                lhs = temp
            if self.emulate_signed:
                self.add_comment('         --- emulate signed ASR')
                if isinstance(rhs, Number):
                    # This emulation adds 2 instructions: JLT, OR (24 ns)
                    # This implementation works only for literal rhs.
                    # It is more efficient than the other emulation below.
                    label = f'asr_end{self._asr_jumps}'
                    self._asr_jumps += 1
                    # save "sign" of lhs
                    if lhs == destination:
                        sign = self.get_temp_reg()
                        self.move(lhs, sign)
                    else:
                        sign = lhs
                    # actually LSR
                    self._add_reg_instruction('asr', lhs, rhs, destination)
                    # add sign extension bits if negative (highest bit set)
                    self.jlt(sign, 0x8000_0000, '@'+label)
                    sign_extension = 0xFFFF_FFFF << (31-rhs)
                    sign_extension &= 0xFFFF_FFFF
                    self.bits_or(destination, sign_extension, destination)
                    self.set_label(label)
                else:
                    # This emulation adds 6 instructions: AND, ASR, NOP, SUB, NOP, OR (56 ns)
                    sign = self.get_temp_reg()
                    sign_extension = self.get_temp_reg()
                    # get sign of lhs (highest bit)
                    self.bits_and(lhs, 0x8000_0000, sign)
                    # actually LSR
                    self._add_reg_instruction('asr', lhs, rhs, destination)
                    # compute sign extension bits
                    self.lsr(sign, rhs, sign)  # explicit unsigned shift
                    zero = self._zero_reg
                    self.sub(zero, sign, sign_extension)
                    self.bits_or(destination, sign_extension, destination)
            else:
                self._add_reg_instruction('asr', lhs, rhs, destination)

    @register_args(signature='II')
    def bits_not(self, source, destination):
        self._add_reg_instruction('not', source, destination)

    @register_args(signature='III')
    def bits_and(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs, rhs = rhs, lhs
        self._add_reg_instruction('and', lhs, rhs, destination)

    @register_args(signature='III')
    def bits_or(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs, rhs = rhs, lhs
        self._add_reg_instruction('or', lhs, rhs, destination)

    @register_args(signature='III')
    def bits_xor(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs, rhs = rhs, lhs
        self._add_reg_instruction('xor', lhs, rhs, destination)

    @register_args(signature='tI')
    def set_mrk(self, time, value):
        self._add_rt_setting('set_mrk', value, time=time)
        self._contains_io_instr = True

    @register_args(signature='t')
    def reset_phase(self, time):
        self._add_rt_setting('reset_ph', time=time)

    @register_args(signature='tFF')
    def awg_offset(self, time, offset0, offset1):
        offset0, offset1 = self._both_reg_or_imm(offset0, offset1)
        last_rt_settings = self._last_rt_settings
        if last_rt_settings.awg_offs_time == time:
            self.add_comment(f'-- Overwrites set_awg_offs at {time} --')
            self._overwrite_rt_setting(last_rt_settings.awg_offs_instr)
        instr = self._add_rt_setting('set_awg_offs', offset0, offset1,
                                     time=time)
        last_rt_settings.awg_offs_time = time
        last_rt_settings.awg_offs_instr = instr
        self._contains_io_instr = True

    @register_args(signature='tFF')
    def awg_gain(self, time, gain0, gain1):
        gain0, gain1 = self._both_reg_or_imm(gain0, gain1)
        last_rt_settings = self._last_rt_settings
        if last_rt_settings.awg_gain_time == time:
            self.add_comment(f'-- Overwrites set_awg_gain at {time} --')
            self._overwrite_rt_setting(last_rt_settings.awg_gain_instr)
        instr = self._add_rt_setting('set_awg_gain', gain0, gain1,
                                     time=time)
        last_rt_settings.awg_gain_time = time
        last_rt_settings.awg_gain_instr = instr

#    @register_args(signature='tI') -- handled in _convert_frequency()
    def set_freq(self, time, frequency):
        ifreq = self._convert_frequency(frequency)
        self._add_rt_setting('set_freq', ifreq, time=time)
        self.modifies_frequency = True

#    @register_args(signature='tFo') -- handled in _convert_phase()
    def set_phase(self, time, phase, hires_regs):
        with self.scope():
            iphase = self._convert_phase(phase, hires_regs)
            self._add_rt_setting('set_ph', iphase, time=time)

#    @register_args(signature='tFo') -- handled in _convert_phase()
    def add_phase(self, time, delta, hires_regs):
        with self.scope():
            iphase = self._convert_phase(delta, hires_regs)
            # FIXME accumulate phase shifts at same time. Currently they are overwritten.
            self._add_rt_setting('set_ph_delta', iphase, time=time)

    @register_args(signature='tI')
    def wait_reg(self, time, register):
        # Note: wait_reg also effectively contains a block_end and block_start.
        elapsed = self._wait_till(time,
                                  pending_update=PendingUpdate.FLUSH,
                                  return_negative=True)
        self._add_wait_reg(register, elapsed)
        # rt_settings may not be overwritten across wait_reg boundary
        self._last_rt_settings.clear()

#    @register_args(signature='too') # -- effectively translates nothing
    def play(self, time, wave0, wave1):
        # if one of them is None, then play same wave as other.
        if wave0 is None:
            wave0 = wave1
        elif wave1 is None:
            wave1 = wave0
        wave0 = self._data.translate_wave(wave0)
        wave1 = self._data.translate_wave(wave1)
        self._add_rt_command('play', wave0, wave1,
                             time=time, updating=True)
        self._contains_io_instr = True

    @register_args(signature='toI')
    def acquire(self, time, acquisition, bin_index):
        acq_index = self._data.translate_acquisition(acquisition)
        self._add_rt_command('acquire',
                             acq_index, bin_index,
                             time=time, updating=True)
        self._contains_io_instr = True

    @register_args(signature='toIoo')
    def acquire_weighed(self, time, acquisition, bin_index, weight0, weight1):
        acq_index = self._data.translate_acquisition(acquisition)
        weight0 = self._data.translate_weight(weight0)
        weight1 = self._data.translate_weight(weight1)
        # q1asm has no instruction for acquire_weighed imm,reg,imm,imm,imme.
        # Use acquire_weighed imm,reg,reg,reg,imm instead
        if not isinstance(bin_index, Number):
            with self._registers.temp_regs(2) as (rw0, rw1):
                self.move(weight0, rw0)
                self.move(weight1, rw1)
                self._add_rt_command('acquire_weighed',
                                     acq_index, bin_index, rw0, rw1,
                                     time=time, updating=True)
        else:
            self._add_rt_command('acquire_weighed',
                                 acq_index, bin_index, weight0, weight1,
                                 time=time, updating=True)
        self._contains_io_instr = True

    @register_args(signature='toIo')
    def acquire_ttl(self, time, acquisition, bin_index, enable):
        acq_index = self._data.translate_acquisition(acquisition)
        self._add_rt_command('acquire_ttl',
                             acq_index, bin_index, enable,
                             time=time, updating=True)
        self._contains_io_instr = True

    @register_args(signature='tI')
    def set_latch_en(self, time, enable):
        self._add_rt_command('set_latch_en', enable, time=time)

    def latch_rst(self, time):
        self._add_rt_command('latch_rst', time=time)

    @contextmanager
    def unsigned_registers(self):
        emulate_signed = self.emulate_signed
        self.emulate_signed = False
        yield
        self.emulate_signed = emulate_signed

    @contextmanager
    def scope(self):
        self._registers.enter_scope()
        yield
        self._registers.exit_scope()

    def get_temp_reg(self):
        ''' Allocates an assembler register for temporary use within scope. '''
        return self._registers.get_temp_reg()

    def temp_regs(self, n):
        return self._registers.temp_regs(n)

    def allocate_reg(self, name):
        return self._registers.allocate_reg(name)

    def _add_reg_comment(self, comment):
        if self._list_registers:
            self._reg_comment = comment

    def _both_reg_or_imm(self, value1, value2):
        # Note: There is an older implementation with for loops that is
        #       much shorter, but this version is mucch faster.
        # Not checked combination: None, None
        if value1 is None:
            if isinstance(value2, int):
                res1 = 0
                res2 = value2
            else:
                # None,reg => reg,reg
                res1 = self._zero_reg
                res2 = value2
        elif isinstance(value1, int):
            if value2 is None:
                res1 = value1
                res2 = 0
            elif isinstance(value2, int):
                res1 = value1
                res2 = value2
            else:
                # imm,reg => reg,reg
                temp = self._registers.get_temp_reg()
                self.move(value1, temp)
                res1 = temp
                res2 = value2
        else:
            # value1 is reg
            if value2 is None:
                # reg,None => reg,reg
                res1 = value1
                res2 = self._zero_reg
            elif isinstance(value2, int):
                # reg,imm => reg,reg
                temp = self._registers.get_temp_reg()
                self.move(value2, temp)
                res1 = value1
                res2 = temp
            else:
                # reg,reg
                res1 = value1
                res2 = value2
        return res1, res2

    def _to_asm_reg(self, operand):
        if isinstance(operand, Register):
            asm_reg = self._registers.get_asm_reg(operand.name)
        elif isinstance(operand, Expression):
            asm_reg = operand.evaluate(self)
        else:
            raise Q1TypeError(f'Illegal operand {operand}')
        return asm_reg

    def _translate_reg(self, value_or_reg):
        if isinstance(value_or_reg, Register):
            return self._registers.get_asm_reg(value_or_reg.name)
        return value_or_reg

    def _oper_to_f16(self, operand):
        if isinstance(operand, Register):
            asm_reg = self._registers.get_asm_reg(operand.name)
            temp_reg = self.get_temp_reg()
            self._add_reg_instruction('asr', asm_reg, 16, temp_reg)
            return temp_reg
        elif isinstance(operand, Expression):
            asm_reg = operand.evaluate(self)
            self._add_reg_instruction('asr', asm_reg, 16, asm_reg)
            return asm_reg
        else:
            raise Q1TypeError(f'Illegal operand {operand}')

    def _convert_frequency(self, frequency):
        if isinstance(frequency, Operand):
            dtype = get_dtype(frequency)
            if dtype is not int:
                raise Exception('frequency must be an integer value')
            if isinstance(frequency, Expression):
                # evaluate expression and store result in register
                reg_freq = Register('_frequency')
                statement = reg_freq.assign(frequency << 2)
                statement.write_instruction(self)
            else:
                reg_freq = frequency << 2
            return reg_freq.evaluate(self)
        else:
            return int(round(frequency*4))

    def _convert_phase(self, phase, hires_regs):
        dtype = get_dtype(phase)
        if dtype is not float:
            raise Exception('phase must be a float value')

        if isinstance(phase, float):
            # convert float range -1.0 ... +1.0 => 5e8 .. 1e9; 0 .. 5e8
            n = int(round((phase+2) * 5e8))
            n %= 1000_000_000
            return n

        if isinstance(phase, Expression):
            # evaluate expression and store result in register
            reg_phase = Register('_phase')
            statement = reg_phase.assign(phase)
            statement.write_instruction(self)
            phase = reg_phase

        if isinstance(phase, Register):
            # use unsigned operations for multiplication
            with self.unsigned_registers():
                # multiply with 1e9
                # first 4 terms: rel. error -1.7e-3
                r1 = (phase >> 2)-(phase >> 5) + (phase >> 6)-(phase >> 9)
                # 6 terms: rel. error -1.8e4
                r1 += (phase >> 11)-(phase >> 13)
                # without hires this takes ~32 cycles = 128 ns
                # with hires it takes ~62 cycles = 248 ns
                if hires_regs:
                    # 11 terms: exact solution!
                    r1 += (phase >> 15) + (phase >> 16)-(phase >> 18)
                    r1 += (phase >> 21) + (phase >> 23)
                return r1.evaluate(self)

    def sim_log(self, msg, register, opt):
        if isinstance(register, Register):
            reg = self._translate_reg(register)
        elif register is None:
            reg = 'none'
        else:
            raise Q1TypeError('Only registers and None can be logged')
        self.add_comment(f'Q1Sim:log "{msg}",{reg},{opt}')

    def _format_line(self, label, mnemonic, args, wait_after, comment, line_nr,
                     compact=False):
        if label is not None:
            label = label+':'
        else:
            label = ''

        arg_list = []
        if args is not None:
            arg_list += [str(p) for p in args]
        if wait_after is not None:
            arg_list += [str(wait_after)]
        arg_str = ','.join(arg_list)

        if compact:
            return f'{label} {mnemonic} {arg_str}'

        c = ''
        if not self.add_comments or (comment is None and not self._line_numbers):
            c = ''
        else:
            c = ' # '
            if self._line_numbers and line_nr is not None:
                c += f'L{line_nr:04} '
            if comment is not None:
                c += comment

        return f'{label:10} {mnemonic:14} {arg_str:10}{c}'

    def q1asm_lines(self, compact=False):
        lines = []
        line_nr = 0
        line_label = None

        for i in self._init_section + self._instructions:
            if isinstance(i, str):
                if i.startswith('Q1Sim:'):
                    lines += [f'#{i} ']
                # comment line
                elif self.add_comments and not compact:
                    lines += [f'# {i} ']
                continue

            if i.label is not None:
                if line_label is not None:
                    raise Q1CompileError('Cannot put two labels on one line '
                                         f'"{i.label}","{line_label}"')
                line_label = i.label
                continue
            if i.overwritten:
                if not compact:
                    lines += [self._format_line('# ------',
                                                i.mnemonic, i.args, i.wait_after,
                                                i.comment, None)]
                continue
            line_nr += 1
            line = self._format_line(line_label, i.mnemonic, i.args, i.wait_after,
                                     i.comment, line_nr, compact)
            line_label = None
            lines += [line]
        return lines

    def assemble(self, listing=False, json_output=False, filename=None):
        if listing:
            self._save_prog_and_data_txt(filename.replace('.json', '.q1asm'))
        if self._optimize > 0 and not self._contains_io_instr:
            # no RT instructions (other than reset_ph): program does nothing
            logger.debug('No RT IO statements')
            self.q1asm = None
        else:
            d = self._data.get_data_dict()
            d['program'] = self._q1asm_prog(compact=True)
            self.q1asm = d
            if json_output:
                self._save_prog_and_data_json(filename)

    def _q1asm_prog(self, compact=False):
        return '\n'.join(self.q1asm_lines(compact))

    def _save_prog_and_data_json(self, filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.q1asm, f, indent=None, separators=(',', ':'))

    def _pprint_data(self, data_dict, f):
        prefix = ' '*12
        f.write('{\n')
        for name, wave in data_dict.items():
            f.write(f"    '{name}':{{\n")
            f.write(f"        'data':\n")
            f.write(prefix)
            # precision of 5 digits is sufficient for 16 bit numbers in range [-1, +1]
            f.write(np.array2string(np.array(wave['data']),
                                    prefix=prefix,
                                    separator=',',
                                    formatter={'float_kind': lambda x: f'{x:9.5f}'},
                                    threshold=1000_000))
            f.write(f",\n")
            f.write(f"        'index':{wave['index']},\n")
            f.write(f'        }},\n')
        f.write('    }\n\n')

    def _save_prog_and_data_txt(self, filename):
        d = self._data.get_data_dict()
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('waveforms=')
            self._pprint_data(d['waveforms'], f)
            f.write('weights=')
            self._pprint_data(d['weights'], f)
            f.write('acquisitions=')
            pprint(d['acquisitions'], f)
            f.write('\n')
            f.write('seq_prog="""\n')
            f.write(self._q1asm_prog())
            f.write('\n"""\n\n')

    def _format_waveforms(self, waveforms):
        waveforms = {}
        for name, wave in self._data.waveforms.items():
            waveforms[name] = wave.copy()
            waveforms[name]['data'] = np.array(wave['data'])
        return waveforms
