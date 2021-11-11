from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class Instruction:
    mnemonic: str
    args: Optional[Tuple[int]] = None
    comment: Optional[str] = None
    label: Optional[str] = None
    wait_after: Optional[int] = None

@dataclass
class PendingUpdate:
    index: str
    time: int


RT_RESOLUTION = 4
MAX_WAIT = (1<<16)-RT_RESOLUTION

class InstructionQueue:
    _check_time_reg = False
    emulate_signed = True

    def __init__(self):
        super().__init__()
        self._init_section = []
        self._instructions = []
        self._reg_comment = None
        self._label = None
        self._wait_loop_cnt = 0
        self._rt_time = 0
        self._pending_update = None
        self._last_rt_command = None

    def add_comment(self, line, init_section=False):
        if init_section:
            self._init_section.append(line)
        else:
            self._instructions.append(line)

    def set_label(self, label):
        '''
        Label to be added to next instruction
        '''
        self._label = label

    def __append_instruction(self, instruction):
        if self._label is not None:
            instruction.label = self._label
            self._label = None
        self._instructions.append(instruction)

    def _add_instruction(self, mnemonic, *args, comment=None, init_section=False):
        if self._reg_comment:
            comment = self._reg_comment if not comment else comment + ' ' + self._reg_comment
            self._reg_comment = None
        instruction = Instruction(mnemonic, args, comment=comment)
        if init_section:
            self._init_section.append(instruction)
            return
        self.__append_instruction(instruction)

    def _add_rt_setting(self, mnemonic, *args, time=None, comment=None):
        instruction = Instruction(mnemonic, args, comment=comment)
        self.__append_instruction(instruction)
        self._schedule_update(time)

    def _add_rt_command(self, mnemonic, *args, time=None, comment=None,
                        index=None):
        self._wait_till(time, merge_update=True)
        wait_after = RT_RESOLUTION
        instruction = Instruction(mnemonic, args, comment=comment, wait_after=wait_after)
        if index is None:
            self.__append_instruction(instruction)
        else:
            self._instructions.insert(index, instruction)
        self._last_rt_command = instruction
        self._rt_time += wait_after

    def _reset_time(self):
        self._flush_pending_update()
        # start counting after the wait_sync statement
        self._rt_time = 0
        self._last_rt_command = None

    def _schedule_update(self, time):
        if self._pending_update is not None and time == self._pending_update.time:
            # put update immediately after rt_setting
            index_update = len(self._instructions)
            # move pending update after last instruction.
            self._pending_update.index = index_update
            return
        self._wait_till(time)
        # put update immediately after rt_setting (but get index after previous pending has been added)
        index_update = len(self._instructions)
        self._pending_update = PendingUpdate(index_update, time)

    def _wait_till(self, time, merge_update=False, return_negative=False):
        if (merge_update
            and self._pending_update is not None
            and time == self._pending_update.time):
            # merge pending update with RT command that follows
            self._pending_update = None
        else:
            self._flush_pending_update()
        wait_time = time - self._rt_time
        if wait_time < 0:
            if return_negative:
                # time will be compensated in register
                self._rt_time = time
                return -wait_time
            raise Exception(f'Too short wait time of {wait_time} ns at {time}')
        if wait_time > 0:
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
#        self.add_comment(f'WAIT {time}')
        if time < 0:
            raise Exception(f'Illegal wait time {time}')
        n_max,rem_wait = divmod(time, MAX_WAIT)
        if n_max == 1:
            self._add_instruction('wait', MAX_WAIT)
        if n_max == 2:
            self._add_instruction('wait', MAX_WAIT)
            self._add_instruction('wait', MAX_WAIT)
        if n_max > 2:
            self._wait_loop_cnt += 1
            with self.temp_regs(1) as wait_reg:
                self._add_instruction('move', n_max, wait_reg)
                label = f'wait{self._wait_loop_cnt}'
                self.set_label(label)
                self._add_instruction('wait', MAX_WAIT)
                self._add_instruction('loop', wait_reg, '@'+label)
        if rem_wait > 0:
            self._add_instruction('wait', rem_wait)

    def _add_wait_reg(self, time_reg, elapsed=0, less_then_65us=False): # @@@ use option less_then_65us
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
            continue_label = f'waitc{self._wait_loop_cnt}'
            if self.emulate_signed:
                self.add_comment('         --- emulate signed')
                with self.temp_regs(1) as temp_reg:
                    self._add_instruction('xor', wait_reg, 0x8000_0000 , temp_reg)
                    self._add_instruction('jge', temp_reg, 0x8000_0000 + RT_RESOLUTION, '@'+continue_label)
            else:
                self._add_instruction('jge', wait_reg, RT_RESOLUTION, '@'+continue_label)
            self._add_instruction('illegal')
            if less_then_65us:
                self._add_instruction('jlt', wait_reg, MAX_WAIT, '@'+continue_label)
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
