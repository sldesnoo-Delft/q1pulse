import json
from pprint import pprint
from numbers import Number
import numpy as np
import math
from functools import wraps
from contextlib import contextmanager

from .generator_data import GeneratorData
from .instruction_queue import InstructionQueue
from .registers import SequencerRegisters
from ..lang.math_expressions import get_dtype, Expression, Operand
from ..lang.generator import GeneratorBase
from ..lang.register import Register
from ..lang.exceptions import (
        Q1ValueError, Q1TypeError,
        Q1Exception, Q1CompileError
        )


def _int_u32(value):
    if value < 0:
        return value + (1<<32)
    return value

def _float_to_f16(value):
    if value < -1.0 or value > 1.0:
        raise Q1ValueError(f'Fixed point value out of range: {value}')
    _f2i16 = (1 << 15) - 0.1
    return math.floor(value * _f2i16)

def _float_to_f32(value):
    if value < -1.0 or value > 1.0:
        raise Q1ValueError(f'Fixed point value out of range: {value}')
    _f2i30 = (1 << 31) - 0.1
    return _int_u32(math.floor(value * _f2i30))


def register_args(signature):
    '''
        Signature:
        I: integer only; Evaluate expression, allow label.
        f: float or int: Evaluate expression, if one float, then all float; label counts as int
        F: float only: Evaluate expressoin, convert to i16
        t: time. No register. No conversion.
        o: object. No register. No conversion.
    '''
    def decorator_register_args(func):
        @wraps(func)
        def func_wrapper(self, *args, **kwargs):
            try:
                # print(f'{func.__name__} {args}')
                args = list(args)
                self._registers.enter_scope()
                comments = []
                opt_type = None
                for i,(arg,atype) in enumerate(zip(args,signature)): # @@@ optimize: atype to index?
                    converted = False
                    if atype in 'to':
                        # argument is time or object. Nothing to translate
                        continue
                    elif atype == 'I':
                        # translate reg, expr. to asm register
                        if isinstance(arg, Operand):
                            if arg.dtype != int:
                                raise Q1TypeError(f'Argument {i} must be of type int ({args[i]})')
                            asm_reg = self._to_asm_reg(arg)
                            args[i] = asm_reg
                            converted = True
                        elif isinstance(arg,str):
                            # label or 'Rxx'
                            pass
                        else:
                            # make unsigned
                            args[i] = _int_u32(arg)
                    elif atype == 'f':
                        # Note: label has dtype int
                        dtype = get_dtype(arg)
                        # check optional all float or all int
                        if opt_type is None:
                            opt_type = dtype
                        elif dtype is not None and dtype != opt_type:
                            raise Q1TypeError(f'Float/int argument mismatch {dtype}<>{opt_type}')
                        if isinstance(arg, Operand):
                            asm_reg = self._to_asm_reg(arg)
                            args[i] = asm_reg
                            converted = True
                        elif dtype == float:
                            args[i] = _float_to_f32(arg)
                            converted = True
                        elif isinstance(arg,str):
                            # label or 'Rxx'
                            pass
                        else:
                            # make unsigned
                            args[i] = _int_u32(arg)
                    elif atype == 'F':
                        if arg is None:
                            pass
                        elif isinstance(arg, Operand):
                            if arg.dtype != float:
                                raise Q1TypeError(f'Argument {i} must be of type float ({args[i]})')
                            asm_reg = self._to_asm_reg(arg)
                            asm_reg = self._reg_to_f16(asm_reg)
                            args[i] = asm_reg
                            converted = True
                        else:
                            args[i] = _float_to_f16(arg)
                            converted = True

                    if self._show_arg_conversions and converted:
                        comments += [f'{arg} -> {args[i]}']

                if self._show_arg_conversions and len(comments) > 0:
                    self.add_comment(' -- args: ' + ', '.join(comments))
                res = func(self, *args, **kwargs)
                self._registers.exit_scope()
                return res
            except Q1Exception as ex:
                msg = f'in call\n    {func.__name__}({",".join(str(arg) for arg in args)})'
                raise Q1CompileError(msg) from ex

        return func_wrapper

    return decorator_register_args


class Q1asmGenerator(InstructionQueue, GeneratorBase):
    def __init__(self, add_comments=False, list_registers=True,
                 line_numbers=True, comment_arg_conversions=False):
        super().__init__()
        self.add_comments = add_comments
        self._list_registers = list_registers
        self._line_numbers = line_numbers
        self._show_arg_conversions = comment_arg_conversions
        self._repetitions = 1
        self._last_rt_settings = {}
        self._data = GeneratorData()
        self._registers = SequencerRegisters(self._add_reg_comment)
        # counter for signed ASR emulation
        self._asr_jumps = 0
        self.add_comment('--INIT--', init_section=True)


    @property
    def repetitions(self):
        return self._repetitions

    @repetitions.setter
    def repetitions(self, value):
        self._repetitions = value

    def start_main(self):
        self._add_rt_command('wait_sync', time=0)
        self._reset_time()
        self.reset_phase(0)
        self.add_comment('--START-- (t=0)')
        self.set_label('_start')
        self.block_start()

        if self._repetitions > 1:
            self.repetitions_reg = self.allocate_reg('_repetitions')
            self.move(self._repetitions, self.repetitions_reg,
                      init_section=True)

    def end_main(self, time):
        if self._finalized:
            return
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
        self._finalized = True

    def block_start(self):
        # Pending updates of the previous block must be updated now.
        # So, updates scheduled at the end of the loop will be updated
        # at the start of the loop or immediately after the loop.
        self._schedule_update(self._rt_time)
        # rt_settings may not be overwritten across block boundary
        self._last_rt_settings = {}

    def block_end(self):
        # NOTE pending update will move to next block start.
        self._last_rt_settings = {}

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
        self._add_instruction('move', source, destination,
                              init_section=init_section)

    @register_args(signature='fff')
    def add(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs,rhs = rhs,lhs
        self._add_instruction('add', lhs, rhs, destination)

    @register_args(signature='fff')
    def sub(self, lhs, rhs, destination):
        # q1asm has no instruction for sub imm,reg,reg. Use sub reg,reg,reg instead
        if isinstance(lhs, Number):
            with self._registers.temp_regs(1) as temp:
                self.move(lhs, temp)
                self._add_instruction('sub', temp, rhs, destination)
        else:
            self._add_instruction('sub', lhs, rhs, destination)

    @register_args(signature='fIf')
    def asl(self, lhs, rhs, destination):
        # q1asm has no instruction for asl imm,reg,reg. Use asl reg,reg,reg instead
        if isinstance(lhs, Number):
            with self._registers.temp_regs(1) as temp:
                self.move(lhs, temp)
                self._add_instruction('asl', temp, rhs, destination)
        else:
            self._add_instruction('asl', lhs, rhs, destination)

    @register_args(signature='fIf')
    def lsr(self, lhs, rhs, destination):
        # NOTE: q1asm asr is unsigned, so actually it is an logical shift right
        if isinstance(lhs, Number):
            # q1asm has no instruction for asr imm,reg,reg. Use asr reg,reg,reg instead
            with self._registers.temp_regs(1) as temp:
                self.move(lhs, temp)
                self._add_instruction('asr', temp, rhs, destination)
        else:
            self._add_instruction('asr', lhs, rhs, destination)

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
                    # This emulation adds 3 instructions: AND, JLT, OR
                    # This implementation works only for literal rhs.
                    # It is more efficient than the other emulation below.
                    label = f'asr_end{self._asr_jumps}'
                    self._asr_jumps += 1
                    sign = self.get_temp_reg()
                    # get sign of lhs
                    self.bits_and(lhs, 0x8000_0000, sign)
                    # actual ASR
                    self._add_instruction('asr', lhs, rhs, destination)
                    # add sign extension bits if negative (highest bit set)
                    self.jlt(sign, 0x8000_0000, '@'+label)
                    sign_extension = 0xFFFF_FFFF << (31-rhs)
                    sign_extension &= 0xFFFF_FFFF
                    self.bits_or(destination, sign_extension, destination)
                    self.set_label(label)
                else:
                    # This emulation adds 6 instructions: AND, ASR, NOP, SUB, NOP, OR
                    sign = self.get_temp_reg()
                    sign_extension = self.get_temp_reg()
                    # get sign of lhs (highest bit)
                    self.bits_and(lhs, 0x8000_0000, sign)
                    # actual ASR
                    self._add_instruction('asr', lhs, rhs, destination)
                    # compute sign extension bits
                    self.lsr(sign, rhs, sign) # explicit unsigned shift
                    zero = self.get_zero_reg()
                    self.sub(zero, sign, sign_extension)
                    self.bits_or(destination, sign_extension, destination)
            else:
                self._add_instruction('asr', lhs, rhs, destination)


    @register_args(signature='II')
    def bits_not(self, source, destination):
        self._add_instruction('not', source, destination)

    @register_args(signature='III')
    def bits_and(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs,rhs = rhs,lhs
        self._add_instruction('and', lhs, rhs, destination)

    @register_args(signature='III')
    def bits_or(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs,rhs = rhs,lhs
        self._add_instruction('or', lhs, rhs, destination)

    @register_args(signature='III')
    def bits_xor(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs,rhs = rhs,lhs
        self._add_instruction('xor', lhs, rhs, destination)

    @register_args(signature='tI')
    def set_mrk(self, time, value):
        self._add_rt_setting('set_mrk', value, time=time, comment=f'@ {time}')

    @register_args(signature='t')
    def reset_phase(self, time):
        self._add_rt_setting('reset_ph', time=time, comment=f'@ {time}')

    @register_args(signature='tFF')
    def awg_offset(self, time, offset0, offset1):
        offset0, offset1 = self._both_reg_or_imm(offset0, offset1)
        last = self._last_rt_settings.get('set_awg_offs')
        if last is not None and last[0] == time:
            self.add_comment(f'-- Overwrites set_awg_offs at {time} --')
            self._overwrite_rt_setting(last[1])
        instr = self._add_rt_setting('set_awg_offs', offset0, offset1,
                                     time=time, comment=f'@ {time}')
        self._last_rt_settings['set_awg_offs'] = (time, instr)

    @register_args(signature='tFF')
    def awg_gain(self, time, gain0, gain1):
        gain0, gain1 = self._both_reg_or_imm(gain0, gain1)
        last = self._last_rt_settings.get('set_awg_gain')
        if last is not None and last[0] == time:
            self.add_comment(f'-- Overwrites set_awg_gain at {time} --')
            self._overwrite_rt_setting(last[1])
        instr = self._add_rt_setting('set_awg_gain', gain0, gain1,
                                     time=time, comment=f'@ {time}')
        self._last_rt_settings['set_awg_gain'] = (time, instr)

#    @register_args(signature='tFo') -- handled in _convert_phase()
    def set_phase(self, time, phase, hires_regs):
        with self.scope():
            v1,v2,v3 = self._convert_phase(phase, hires_regs)
            self._add_rt_setting('set_ph', v1, v2, v3,
                                 time=time, comment=f'@ {time}')

#    @register_args(signature='tFo') -- handled in _convert_phase()
    def add_phase(self, time, delta, hires_regs):
        with self.scope():
            v1,v2,v3 = self._convert_phase(delta, hires_regs)
            self._add_rt_setting('set_ph_delta', v1, v2, v3,
                                 time=time, comment=f'@ {time}')

    @register_args(signature='tI')
    def wait_reg(self, time, register):
        # Note: wait_reg also effectively contains a block_end and block_start.
        elapsed = self._wait_till(time, pending_update='flush', return_negative=True)
        self._add_wait_reg(register, elapsed)
        # rt_settings may not be overwritten across wait_reg boundary
        self._last_rt_settings = {}

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
                             time=time, comment=f't={time}')

    @register_args(signature='toI')
    def acquire(self, time, section, bin_index):
        section = self._data.translate_acquisition(section)
        self._add_rt_command('acquire',
                             section, bin_index,
                             time=time, comment=f't={time}')

    @register_args(signature='toIoo')
    def acquire_weighed(self, time, bins, bin_index, weight0, weight1):
        bins = self._data.translate_acquisition(bins)
        weight0 = self._data.translate_weight(weight0)
        weight1 = self._data.translate_weight(weight1)
        # q1asm has no instruction for acquire_weighed imm,reg,imm,imm,imme.
        # Use acquire_weighed imm,reg,reg,reg,imm instead
        if not isinstance(bin_index, Number):
            with self._registers.temp_regs(2) as (rw0, rw1):
                self.move(weight0, rw0)
                self.move(weight1, rw1)
                self._add_rt_command('acquire_weighed',
                                     bins, bin_index, rw0, rw1,
                                     time=time, comment=f't={time}')
        else:
            self._add_rt_command('acquire_weighed',
                                 bins, bin_index, weight0, weight1,
                                 time=time, comment=f't={time}')

    @contextmanager
    def unsigned_registers(self):
        emulate_signed = self.emulate_signed
        self.emulate_signed = False
        yield
        self.emulate_signed = emulate_signed

    def enter_scope(self):
        self._registers.enter_scope()

    def exit_scope(self):
        self._registers.exit_scope()

    @contextmanager
    def scope(self):
        self.enter_scope()
        yield
        self.exit_scope()

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
        if value1 is None:
            if isinstance(value2, int):
                res1 = 0
                res2 = value2
            else:
                # None,reg => reg,reg
                res1 = self.get_zero_reg()
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
                res2 = self.get_zero_reg()
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
        return res1,res2

    def get_zero_reg(self):
        asm_reg, init_reg = self._registers.get_zero_reg()
        if init_reg:
            self._add_instruction('move', 0, asm_reg, init_section=True)
        return asm_reg

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

    def _reg_to_f16(self, reg):
        temp_reg = self.get_temp_reg()
        self._add_instruction('asr', reg, 16, temp_reg)
        return temp_reg

    def _convert_phase(self, phase, hires_regs):
        # convert float range -1.0 ... +1.0 => 200 ... 399; 0 ... 199
        if isinstance(phase, float):
            n = int(round((phase+2) * 5e8))
            n1,nr = divmod(n, 400*6250)
            n1 %= 400
            n2,n3 = divmod(nr, 6250)
            return n1,n2,n3

        self.add_comment('         --- phase register -> 3 phase instruction arguments')

        if isinstance(phase, Expression):
            # evaluate expression and store result in register
            reg_phase = Register(f'_phase')
            statement = reg_phase.assign(phase)
            statement.write_instruction(self)
            phase = reg_phase

        if isinstance(phase, Register):
            # use unsigned operations for multiplication
            with self.unsigned_registers():
                # shift N bits right to create space for multiplication
                N = 10
                # multiply with 400
                r1 = (phase >> (N-4)) + (phase >> (N-7)) + (phase >> (N-8))
                # add small amount for proper rounding
                r1 += 3.5/(1<<31)
                if not hires_regs:
                    r1 >>= (32-N)
                    r2 = self.get_zero_reg()
                    r3 = r2
                    return r1.evaluate(self), r2, r3
                else:
                    rem1 = r1 << N
                    r1 >>= (32-N)
                    # multiply with 400
                    r2 = (rem1 >> (N-4)) + (rem1 >> (N-7)) + (rem1 >> (N-8))
                    # add small amount for proper rounding
                    r2 += 3.5/(1<<31)
                    r2 >>= (32-N)
                    r3 = self.get_zero_reg()
                    return r1.evaluate(self), r2.evaluate(self), r3

    def sim_log(self, msg, register, opt):
        if isinstance(register, Register):
            reg = self._translate_reg(register)
        elif register is None:
            reg = 'none'
        else:
            raise Q1TypeError('Only registers and None can be logged')
        self.add_comment(f'Q1Sim:log "{msg}",{reg},{opt}')

    def _format_line(self, label, mnemonic, args, wait_after, comment, line_nr):
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

    def q1asm_lines(self, skip_comment_lines=False):
        lines = []
        line_nr = 0
        line_label = None

        for i in self._init_section + self._instructions:
            if isinstance(i, str):
                if i.startswith('Q1Sim:'):
                    lines += [f'#{i} ']
                # comment line
                elif self.add_comments and not skip_comment_lines:
                    lines += [f'# {i} ']
                continue

            if i.label is not None:
                if line_label is not None:
                    raise Q1CompileError('Cannot put two labels on one line '
                                         f'"{i.label}","{line_label}"')
                line_label = i.label
                continue
            if i.overwritten:
                lines+= [self._format_line('# ------',
                                           i.mnemonic, i.args, i.wait_after,
                                           i.comment, None)]
                continue
            line_nr += 1
            line = self._format_line(line_label, i.mnemonic, i.args, i.wait_after,
                                     i.comment, line_nr)
            line_label = None
            lines += [line]
        return lines

    def q1asm_prog(self, skip_comment_lines=False):
        return '\n'.join(self.q1asm_lines(skip_comment_lines))

    def save_prog_and_data_json(self, filename):
        d = self._data.get_data_dict()
        d['program'] = self.q1asm_prog(skip_comment_lines=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=None)

    def _pprint_data(self, data_dict, f):
        prefix = ' '*12
        f.write('{\n')
        for name,wave in data_dict.items():
            f.write(f"    '{name}':{{\n")
            f.write(f"        'data':\n")
            f.write(prefix)
            # precision of 5 digits is sufficient for 16 bit numbers in range [-1, +1]
            f.write(np.array2string(np.array(wave['data']),
                                    prefix=prefix,
                                    separator=',',
                                    formatter={'float_kind':lambda x: f'{x:9.5f}'},
                                    threshold=1000_000))
            f.write(f",\n")
            f.write(f"        'index':{wave['index']},\n")
            f.write(f'        }},\n')
        f.write('    }\n\n')

    def save_prog_and_data_txt(self, filename):
        d = self._data.get_data_dict()
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('waveforms=')
            self._pprint_data(d['waveforms'], f)
            f.write('weights=')
            self._pprint_data(d['weights'], f)
            f.write('acquisitions=')
            pprint(d['acquisitions'], f)
            f.write('\n')
            f.write(f'seq_prog="""\n')
            f.write(self.q1asm_prog())
            f.write('\n"""\n\n')

    def _format_waveforms(self, waveforms):
        waveforms = {}
        for name, wave in self._data.waveforms.items():
            waveforms[name] = wave.copy()
            waveforms[name]['data'] = np.array(wave['data'])
        return waveforms
