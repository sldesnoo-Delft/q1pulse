from dataclasses import dataclass

from q1pulse.lang.exceptions import (
        Q1InternalError,
        Q1TimingError
        )


@dataclass
class Instruction:
    mnemonic: str
    args: tuple[int] | None = None
    comment: str | None = None
    label: str | None = None
    wait_after: int | None = None
    overwritten: bool = False


@dataclass
class PendingUpdate:
    KEEP = 0
    MERGE = 1
    FLUSH = 2
    index: int
    time: int


RT_RESOLUTION = 4
MAX_WAIT = (1 << 16) - RT_RESOLUTION


class InstructionQueue:
    _check_time_reg = True
    emulate_signed = True

    def __init__(self, add_comments=False):
        self.add_comments = add_comments
        self._init_section = []
        self._instructions = []
        self._reg_comment = None
        self._wait_loop_cnt = 0
        self._rt_time = 0
        self._pending_update = None
        self._last_rt_command = None
        self._n_rt_instructions = 0
        self._updating_reg = None

    def add_comment(self, line, init_section=False):
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
        self._wait_register_updates(instruction)
        self._instructions.append(instruction)

    def _add_reg_instruction(self, mnemonic, *args, init_section=False):
        if self._reg_comment:
            comment = self._reg_comment
            self._reg_comment = None
        else:
            comment = None
        instruction = Instruction(mnemonic, args, comment=comment)
        if init_section:
            self._init_section.append(instruction)
            return
        self.__append_instruction(instruction)
        self._updating_reg = args[-1]

    def _add_instruction(self, mnemonic, *args, comment=None):
        instruction = Instruction(mnemonic, args, comment=comment)
        self.__append_instruction(instruction)

    def _add_rt_setting(self, mnemonic, *args, time=None):
        if self.add_comments:
            comment = f'@ {time}'
        else:
            comment = None
        instruction = Instruction(mnemonic, args, comment=comment)
        self.__append_instruction(instruction)
        self._schedule_update(time)
        return instruction

    def _add_rt_command(self, mnemonic, *args, time=None, updating=False):
        self._wait_till(time,
                        pending_update=PendingUpdate.MERGE if updating else PendingUpdate.FLUSH)
        wait_after = RT_RESOLUTION
        if self.add_comments:
            comment = f't={time}'
        else:
            comment = None
        instruction = Instruction(mnemonic, args, comment=comment, wait_after=wait_after)
        self.__append_instruction(instruction)
        self._last_rt_command = instruction
        self._n_rt_instructions += 1
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

    def _wait_till(self, time, pending_update=PendingUpdate.KEEP, return_negative=False):
        if self._pending_update is not None:
            if time == self._pending_update.time:
                if pending_update == PendingUpdate.KEEP:
                    return
                elif pending_update == PendingUpdate.MERGE:
                    # merge pending update with RT command that follows
                    self._pending_update = None
                    self._last_rt_command = None
                    self._rt_time = time
                    return
                elif pending_update != PendingUpdate.FLUSH:
                    Q1InternalError(f'Unknown {pending_update}')
            self._flush_pending_update()
        wait_time = time - self._rt_time
        if wait_time > 0:
            if self._last_rt_command is not None:
                if self._last_rt_command.wait_after + wait_time <= MAX_WAIT:
                    self._last_rt_command.wait_after += wait_time
                else:
                    rem_wait_time = wait_time - MAX_WAIT + self._last_rt_command.wait_after
                    self._last_rt_command.wait_after = MAX_WAIT
                    self.__add_wait_instruction(rem_wait_time)
            else:
                self.__add_wait_instruction(wait_time)
        elif wait_time < 0:
            if return_negative:
                # time will be compensated in register
                self._rt_time = time
                return -wait_time
            raise Q1TimingError(f'Too short wait time of {wait_time} ns at t={self._rt_time}')
        self._last_rt_command = None
        self._rt_time = time
        return 0

    def _flush_pending_update(self):
        pending_update = self._pending_update
        if pending_update is not None:
            wait_after = RT_RESOLUTION
            if self.add_comments:
                comment = f't={pending_update.time}'
            else:
                comment = None
            instruction = Instruction('upd_param',  wait_after=wait_after, comment=comment)
            self._instructions.insert(pending_update.index, instruction)
            self._n_rt_instructions += 1
            self._pending_update = None
            self._last_rt_command = instruction
            self._rt_time += wait_after

    def __add_wait_instruction(self, time):
        if time < MAX_WAIT:
            self._add_instruction('wait', time)
            self._n_rt_instructions += 1
        else:
            n_max, rem_wait = divmod(time, MAX_WAIT)
            if n_max <= 2:
                for _ in range(n_max):
                    self._add_instruction('wait', MAX_WAIT)
            else:
                self._wait_loop_cnt += 1
                with self.temp_regs(1) as wait_reg:
                    self._add_reg_instruction('move', n_max, wait_reg)
                    label = f'wait{self._wait_loop_cnt}'
                    self.set_label(label)
                    self._add_instruction('wait', MAX_WAIT)
                    self._add_instruction('loop', wait_reg, '@'+label)
            self._n_rt_instructions += n_max
            if rem_wait > 0:
                self._add_instruction('wait', rem_wait)
                self._n_rt_instructions += 1

    def _add_wait_reg(self, time_reg, elapsed=0, less_then_65us=False):  # @@@ make use of option less_then_65us
        self._n_rt_instructions += 1  # this is not correct if > 65 us.
        if less_then_65us and elapsed == 0 and not self._check_time_reg:
            # single instruction for short simple wait
            self._add_instruction('wait', time_reg)
            return

        wait_reg = self.allocate_reg('_waittime')
        if elapsed > 0:
            self._add_reg_instruction('sub', time_reg, elapsed, wait_reg)
        else:
            self._add_reg_instruction('move', time_reg, wait_reg)
        self._wait_loop_cnt += 1

        if self._check_time_reg:
            self.add_comment('         --- check for negative wait time')
            continue_label = f'waitc{self._wait_loop_cnt}'
            if self.emulate_signed:
                self.add_comment('         --- emulate signed wait time')
                with self.temp_regs(1) as temp_reg:
                    self._add_reg_instruction('xor', wait_reg, 0x8000_0000, temp_reg)
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
            self._add_reg_instruction('sub', wait_reg, MAX_WAIT-RT_RESOLUTION, wait_reg)
            self._add_instruction('jge', wait_reg, MAX_WAIT, '@'+loop_label)
            self.set_label(end_label)

        self._add_instruction('wait', wait_reg)

    def _wait_register_updates(self, instruction):
        '''
        Inserts a NOP when one of the arguments is a register which
        has been modified by the previous instruction.
        Registers are modified by the arithmetic instructions.
        '''
        if self._updating_reg is not None and self._updating_reg in instruction.args:
            self._add_instruction('nop',
                                  comment=f' {instruction.mnemonic} wait for {self._updating_reg}')
        self._updating_reg = None
