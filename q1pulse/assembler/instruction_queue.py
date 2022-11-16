from dataclasses import dataclass
from typing import Optional, Tuple

from ..lang.exceptions import (
        Q1StateError,
        Q1InternalError,
        Q1TimingError
        )

@dataclass
class Instruction:
    mnemonic: str
    args: Optional[Tuple[int]] = None
    comment: Optional[str] = None
    label: Optional[str] = None
    wait_after: Optional[int] = None
    overwritten: bool = False

@dataclass
class PendingUpdate:
    index: str
    time: int


RT_RESOLUTION = 4
MAX_WAIT = (1<<16)-RT_RESOLUTION

class InstructionQueue:
    _check_time_reg = True
    emulate_signed = True

    def __init__(self, add_comments=False):
        super().__init__()
        self.add_comments = add_comments
        self._init_section = []
        self._instructions = []
        self._reg_comment = None
        self._wait_loop_cnt = 0
        self._rt_time = 0
        self._pending_update = None
        self._last_rt_command = None
        self._finalized = False
        self._updating_reg = None
        self._n_rt_instr = 0

    def add_comment(self, line, init_section=False):
        if not self.add_comments:
            return
        if self._finalized:
            raise Q1StateError('Sequence already finalized')
        if init_section:
            self._init_section.append(line)
        else:
            self._instructions.append(line)

    def set_label(self, label):
        '''
        Label to be added to next instruction
        '''
        self._instructions.append(Instruction(None, label=label))

    def adjust_time(self, duration):
        self._rt_time += duration

    def __append_instruction(self, instruction):
        if self._finalized:
            raise Q1StateError('Sequence already finalized')
        self._wait_register_updates(instruction.mnemonic, instruction.args)
        self._instructions.append(instruction)

    def _add_instruction(self, mnemonic, *args, comment=None, init_section=False):
        if self._finalized:
            raise Q1StateError('Sequence already finalized')
        if self._reg_comment:
            comment = self._reg_comment if not comment else comment + ' ' + self._reg_comment
            self._reg_comment = None
        instruction = Instruction(mnemonic, args, comment=comment)
        if init_section:
            self._init_section.append(instruction)
            return
        self.__append_instruction(instruction)
        if mnemonic in ['move','not','add','sub','and','or','xor','asl','asr']:
            self._updating_reg = args[-1]

    def _add_rt_setting(self, mnemonic, *args, time=None):
        self._n_rt_instr += 1
        if self.add_comments:
            comment = f'@ {time}'
        else:
            comment = None
        instruction = Instruction(mnemonic, args, comment=comment)
        self.__append_instruction(instruction)
        self._schedule_update(time)
        return instruction

    def _add_rt_command(self, mnemonic, *args, time=None, index=None):
        self._n_rt_instr += 1
        self._wait_till(time, pending_update='merge')
        wait_after = RT_RESOLUTION
        if self.add_comments:
            comment = f't={time}'
        else:
            comment = None
        instruction = Instruction(mnemonic, args, comment=comment, wait_after=wait_after)
        if index is None:
            self.__append_instruction(instruction)
        else:
            self._instructions.insert(index, instruction)
        self._last_rt_command = instruction
        self._rt_time += wait_after

    def _overwrite_rt_setting(self, instruction):
        instruction.overwritten = True
        if self.add_comments:
            instruction.comment += ' = overwritten ='

    def _reset_time(self):
        self._flush_pending_update()
        # start counting after the wait_sync statement
        self._rt_time = 0
        self._last_rt_command = None

    def _schedule_update(self, time):
        self._wait_till(time)
        # put new update immediately after rt_setting (but get index after previous pending has been added)
        index_update = len(self._instructions)
        self._pending_update = PendingUpdate(index_update, time)

    def _wait_till(self, time, pending_update='keep', return_negative=False):
        if (self._pending_update is not None
            and time == self._pending_update.time):
            if pending_update == 'keep':
                return
            elif pending_update == 'merge':
                # merge pending update with RT command that follows
                self._pending_update = None
                self._last_rt_command = None
                self._rt_time = time
                return
            elif pending_update != 'flush':
                Q1InternalError(f'Unknown {pending_update}')
        self._flush_pending_update()
        wait_time = time - self._rt_time
        if wait_time < 0:
            if return_negative:
                # time will be compensated in register
                self._rt_time = time
                return -wait_time
            raise Q1TimingError(f'Too short wait time of {wait_time} ns at t={self._rt_time}')
        if wait_time > 0:
            if wait_time > 50000:
                self.add_comment(f'wait {wait_time} (t={time})')
            if self._last_rt_command is not None:
                if self._last_rt_command.wait_after + wait_time < MAX_WAIT:
                    self._last_rt_command.wait_after += wait_time
                else:
                    rem_wait_time = wait_time - MAX_WAIT + self._last_rt_command.wait_after
                    self._last_rt_command.wait_after = MAX_WAIT
                    self.__add_wait_instruction(rem_wait_time)
            else:
                self.__add_wait_instruction(wait_time)
        self._last_rt_command = None
        self._rt_time = time
        return 0

    def _flush_pending_update(self):
        pending_update = self._pending_update
        if pending_update is not None:
            wait_after = RT_RESOLUTION
            instruction = Instruction('upd_param',  wait_after=wait_after, comment=f't={pending_update.time}')
            self._instructions.insert(pending_update.index, instruction)
            self._pending_update = None
            self._last_rt_command = instruction
            self._rt_time += wait_after

    def __add_wait_instruction(self, time):
        if time < 0:
            raise Q1InternalError(f'Illegal wait time {time}')
        n_max,rem_wait = divmod(time, MAX_WAIT)
        if n_max <= 2:
            for _ in range(n_max):
                self._add_instruction('wait', MAX_WAIT)
        else:
            self._wait_loop_cnt += 1
            with self.temp_regs(1) as wait_reg:
                self._add_instruction('move', n_max, wait_reg)
                label = f'wait{self._wait_loop_cnt}'
                self.set_label(label)
                self._add_instruction('wait', MAX_WAIT)
                self._add_instruction('loop', wait_reg, '@'+label)
        if rem_wait > 0:
            self._add_instruction('wait', rem_wait)

    def _add_wait_reg(self, time_reg, elapsed=0, less_then_65us=False): # @@@ make use of option less_then_65us
        if less_then_65us and elapsed == 0 and not self._check_time_reg:
            # single instruction for short simple wait
            self._add_instruction('wait', time_reg)
            return

        wait_reg = self.allocate_reg('_waittime')
        if elapsed > 0:
            self._add_instruction('sub', time_reg, elapsed, wait_reg)
        else:
            self._add_instruction('move', time_reg, wait_reg)
        self._wait_loop_cnt += 1

        if self._check_time_reg:
            self.add_comment('         --- check for negative wait time')
            continue_label = f'waitc{self._wait_loop_cnt}'
            if self.emulate_signed:
                self.add_comment('         --- emulate signed wait time')
                with self.temp_regs(1) as temp_reg:
                    self._add_instruction('xor', wait_reg, 0x8000_0000, temp_reg)
                    self._add_instruction('jge', temp_reg, 0x8000_0000 + RT_RESOLUTION, '@'+continue_label)
            else:
                self._add_instruction('jge', wait_reg, RT_RESOLUTION, '@'+continue_label)
            self._add_instruction('illegal', comment='negative wait time')
            if less_then_65us:
                self._add_instruction('jlt', wait_reg, MAX_WAIT, '@'+continue_label)
                self._add_instruction('illegal', comment='larger than 65 us')
            self.set_label(continue_label)

        if not less_then_65us:
            loop_label = f'wait{self._wait_loop_cnt}'
            end_label = f'endwait{self._wait_loop_cnt}'
            self._add_instruction('jlt', wait_reg, MAX_WAIT, '@'+end_label)
            self.set_label(loop_label)
            self._add_instruction('wait', MAX_WAIT-RT_RESOLUTION)
            self._add_instruction('sub', wait_reg, MAX_WAIT-RT_RESOLUTION, wait_reg)
            self._add_instruction('jge', wait_reg, MAX_WAIT, '@'+loop_label)
            self.set_label(end_label)

        self._add_instruction('wait', wait_reg)

    def _wait_register_updates(self, mnemonic, args):
        '''
        Inserts a NOP when one of the arguments is a register which
        has been modified by the previous instruction.
        Registers are modified by the arithmetic instructions.
        '''
        if self._updating_reg is not None and self._updating_reg in args:
            self._add_instruction('nop', comment=f' {mnemonic} wait for {self._updating_reg}')
        self._updating_reg = None
