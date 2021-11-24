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
from ..model.math_expressions import get_dtype, Expression
from ..model.generator import GeneratorBase
from ..model.register import Register
from ..model.sequencer_data import Wave, AcquisitionBins, AcquisitionWeight

# TODO @@ reset_time() for start of loop / set_time() for continuation after loop. ??

def _int_u32(value):
    if value < 0:
        value += 1<<32
    return value

def _int_u16(value):
#    if value < 0:
#        value += 1<<16
    return value

def _float_to_f16(value):
    if value < -1.0 or value > 1.0:
        raise Exception(f'Fixed point value out of range: {value}')
    _f2i16 = (1 << 15) - 0.1
    return _int_u16(math.floor(value * _f2i16))

def _float_to_f32(value):
    if value < -1.0 or value > 1.0:
        raise Exception(f'Fixed point value out of range: {value}')
    _f2i30 = (1 << 31) - 0.1
    return _int_u32(math.floor(value * _f2i30))


def register_args(_func=None, *, allow_float=[], require_float=[]):

    def decorator_register_args(func):
        @wraps(func)
        def func_wrapper(self, *args, **kwargs):
            # print(f'{func.__name__}{args}')
            args = list(args)
            kwargs = kwargs.copy()
            self._registers.enter_scope()
            comments = []
            floats = []
            for i,arg in enumerate(args):
                index = i+1
                dtype = get_dtype(arg)
                if dtype == float:
                    if index in allow_float:
                        floats.append(index)
                else:
                    if index in require_float and arg is not None:
                        raise Exception(f'Float argument required for arg {index} ({arg})')

                if isinstance(arg, (str, type(None),
                                    Wave, AcquisitionBins, AcquisitionWeight)):
                    pass
                elif isinstance(arg, int):
                    args[i] = _int_u32(arg)
                elif isinstance(arg, float):
                    if index in allow_float:
                        args[i] = _float_to_f32(arg)
                    elif index in require_float:
                        args[i] = _float_to_f16(arg)
                    else:
                        raise Exception(f'Float argument not allowed for arg {index} ({args[i]})')
                    comments += [f'{arg} -> {args[i]}']
                else:
                    if isinstance(arg, Register):
                        asm_reg = self._translate_reg(arg)
                    elif isinstance(arg, Expression):
                        expression = arg
                        asm_reg = expression.evaluate(self)
                    else:
                        raise Exception(f'Illegal argument type for arg {index}: {args}')
                    if index in require_float:
                        asm_reg = self._reg_to_f16(asm_reg)
                    comments += [f'{asm_reg}:{dtype.__name__}={arg}']
                    args[i] = asm_reg

            if len(floats) > 0:
                for f in floats:
                    if f not in allow_float:
                        raise Exception(f'Float argument mismatch for argument {f}')

            if len(comments) > 0 and self._show_arg_conversions:
                self.add_comment(' -- args: ' + ', '.join(comments))
            res = func(self, *args, **kwargs)
            self._registers.exit_scope()
            return res

        return func_wrapper

    if _func is None:
        return decorator_register_args
    else:
        return decorator_register_args(_func)


class Q1asmGenerator(InstructionQueue, GeneratorBase):
    def __init__(self, add_comments=False, list_registers=True,
                 line_numbers=True, comment_arg_conversions=False):
        super().__init__()
        self.add_comments = add_comments
        self._list_registers = list_registers
        self._line_numbers = line_numbers
        self._show_arg_conversions = comment_arg_conversions
        self._repetitions = 1
        self._data = GeneratorData()
        self._registers = SequencerRegisters(self._add_reg_comment)
        self.add_comment('--INIT--', init_section=True)

    @property
    def repetitions(self):
        return self._repetitions

    @repetitions.setter
    def repetitions(self, value):
        self._repetitions = value

    def start_main(self):
        self._add_rt_command('wait_sync', time=0)
        self.set_label('_start')
        self.reset_phase(4)
        self._reset_time()
        self.add_comment('--START-- (t=0)')

        if self._repetitions > 1:
            self.repetitions_reg = self.allocate_reg('_repetitions')
            self.move(self._repetitions, self.repetitions_reg,
                      init_section=True)

    def finalize(self):
        if self._finalized:
            return
        self._flush_pending_update()
        if self._repetitions > 1:
            self.loop(self.repetitions_reg, '_start')
        self._add_instruction('stop')
        self._finalized = True

    def jmp(self, label):
        label = self._translate_label(label)
        self._add_instruction('jmp', label)

    @register_args(allow_float=(1,2))
    def jlt(self, register, value, label):
        label = self._translate_label(label)
        self._add_instruction('jlt', register, value, label)

    @register_args(allow_float=(1,2))
    def jge(self, register, value, label):
        label = self._translate_label(label)
        self._add_instruction('jge', register, value, label)

    @register_args
    def loop(self, register, label):
        label = self._translate_label(label)
        self._add_instruction('loop', register, label)

    @register_args(allow_float=(1,2))
    def move(self, source, destination, init_section=False):
        self._add_instruction('move', source, destination,
                              init_section=init_section)

    @register_args(allow_float=(1,2,3))
    def add(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs,rhs = rhs,lhs
        self._add_instruction('add', lhs, rhs, destination)

    @register_args(allow_float=(1,2,3))
    def sub(self, lhs, rhs, destination):
        # q1asm has no instruction for sub imm,reg,reg. Use sub reg,reg,reg instead
        if isinstance(lhs, Number):
            with self._registers.temp_regs(1) as temp:
                self.move(lhs, temp)
                self._add_instruction('sub', temp, rhs, destination)
        else:
            self._add_instruction('sub', lhs, rhs, destination)

    @register_args(allow_float=(1,3))
    def asl(self, lhs, rhs, destination):
        # q1asm has no instruction for asl imm,reg,reg. Use asl reg,reg,reg instead
        if isinstance(lhs, Number):
            with self._registers.temp_regs(1) as temp:
                self.move(lhs, temp)
                self._add_instruction('asl', temp, rhs, destination)
        else:
            self._add_instruction('asl', lhs, rhs, destination)

    @register_args(allow_float=(1,3))
    def asr(self, lhs, rhs, destination):
        # q1asm has no instruction for asr imm,reg,reg. Use asr reg,reg,reg instead
        if isinstance(lhs, Number):
            with self._registers.temp_regs(1) as temp:
                self.move(lhs, temp)
                self._add_instruction('asr', temp, rhs, destination)
        else:
            self._add_instruction('asr', lhs, rhs, destination)

    @register_args
    def bits_not(self, source, destination):
        self._add_instruction('not', source, destination)

    @register_args
    def bits_and(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs,rhs = rhs,lhs
        self._add_instruction('and', lhs, rhs, destination)

    @register_args
    def bits_or(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs,rhs = rhs,lhs
        self._add_instruction('or', lhs, rhs, destination)

    @register_args
    def bits_xor(self, lhs, rhs, destination):
        if isinstance(lhs, int):
            # swap arguments. 1st argument cannot be immediate value
            lhs,rhs = rhs,lhs
        self._add_instruction('xor', lhs, rhs, destination)

    @register_args
    def set_mrk(self, time, value):
        self._add_rt_setting('set_mrk', value, time=time, comment=f'@ {time}')

    def reset_phase(self, time):
        self._add_rt_setting('reset_ph', time=time, comment=f'@ {time}')

    @register_args(require_float=(2,3))
    def awg_offset(self, time, offset0, offset1):
        offset0, offset1 = self._all_reg_or_imm(offset0, offset1)
        self._add_rt_setting('set_awg_offs', offset0, offset1,
                             time=time, comment=f'@ {time}')

    @register_args(require_float=(2,3))
    def awg_gain(self, time, gain0, gain1):
        gain0, gain1 = self._all_reg_or_imm(gain0, gain1)
        self._add_rt_setting('set_awg_gain', gain0, gain1,
                             time=time, comment=f'@ {time}')

#    @register_args(allow_float=(2,)) -- handled in _convert_phase()
    def set_phase(self, time, phase, hires_regs):
        with self.scope():
            v1,v2,v3 = self._convert_phase(phase, hires_regs)
            self._add_rt_setting('set_ph', v1, v2, v3,
                                 time=time, comment=f'@ {time}')

#    @register_args(allow_float=(2,)) -- handled in _convert_phase()
    def add_phase(self, time, delta, hires_regs):
        with self.scope():
            v1,v2,v3 = self._convert_phase(delta, hires_regs)
            self._add_rt_setting('set_ph_delta', v1, v2, v3,
                                 time=time, comment=f'@ {time}')

    @register_args
    def wait_reg(self, time, register):
        elapsed = self._wait_till(time, return_negative=True)
        self._add_wait_reg(register, elapsed)

    def wait_till(self, time):
        self._wait_till(time)

    def play(self, time, wave0, wave1):
        wave0, wave1 = self._data.translate_waves(wave0, wave1)
        wave0, wave1 = self._all_reg_or_imm(wave0, wave1)
        self._add_rt_command('play', wave0, wave1,
                             time=time, comment=f't={time}')

    @register_args
    def acquire(self, time, section, bin_index):
        section = self._data.translate_acquisition(section)
        self._add_rt_command('acquire',
                             section, bin_index,
                             time=time, comment=f't={time}')

    @register_args
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

    def _all_reg_or_imm(self, *operands):
        t = None
        result = []
        for o in operands:
            result.append(o)
            if isinstance(o, int):
                if t == 'reg':
                    raise Exception(f'Illegal arguments {operands}')
                t = 'imm'
            if isinstance(o, str):
                if t == 'imm':
                    raise Exception(f'Illegal arguments {operands}')
                t = 'reg'

        if t is None:
            raise Exception(f'Illegal arguments {operands}')

        for i,o in enumerate(result):
            if o is None:
                if t == 'imm':
                    result[i] = 0
                else:
                    result[i] = self._get_dummy_reg()

        return result

    def _get_dummy_reg(self):
        asm_reg, init_reg = self._registers.get_dummy_reg()
        if init_reg:
            self._add_instruction('move', 0, asm_reg, init_section=True)
        return asm_reg

    def _translate_label(self, label):
        if isinstance(label, str):
            return f'@{label}'
        return self._translate_reg(label)

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

        if isinstance(phase, Expression):
            reg_phase = Register(f'_phase')
            statement = reg_phase.assign(phase)
            statement.write_instruction(self)
            phase = reg_phase

        if isinstance(phase, Register):
            # shift N bits right to create space for multiplication
            N = 10
            # multiply with 400
            r1 = (phase >> (N-4)) + (phase >> (N-7)) + (phase >> (N-8))
            # add small amount for proper rounding
            r1 += 3.5/(1<<31)
            if not hires_regs:
                r1 >>= (32-N)
                r2 = self._get_dummy_reg()
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
                r3 = self._get_dummy_reg()
                return r1.evaluate(self), r2.evaluate(self), r3


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
            if self._line_numbers:
                c += f'L{line_nr:04} '
            if comment is not None:
                c += comment

        return f'{label:10} {mnemonic:14} {arg_str:10}{c}'

    def q1asm_lines(self, skip_comment_lines=False):
        self.finalize()
        lines = []
        line_nr = 0

        for i in self._init_section + self._instructions:
            if isinstance(i, str):
                # comment line
                if self.add_comments and not skip_comment_lines:
                    lines += [f'# {i} ']
                continue

            line_nr += 1
            line = self._format_line(i.label, i.mnemonic, i.args, i.wait_after,
                                     i.comment, line_nr)

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
