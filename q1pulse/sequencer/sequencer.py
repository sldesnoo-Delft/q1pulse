import sys
import os
import logging
import traceback
from copy import copy
from contextlib import contextmanager
from types import NoneType

from .builderbase import BuilderBase
from q1pulse.lang.triggers import TriggerCounter
from q1pulse.lang.conditions import (
        LatchEnableStatement, LatchResetStatement,
        BranchSequence, ConditionalBlockStatement,
        CounterFlags,
        )
from q1pulse.lang.exceptions import (
        Q1StateError, Q1Exception,
        Q1InternalError, Q1SequenceError,
        Q1SyntaxError, Q1TimingError
        )
from q1pulse.lang.feedback import (
    FeedbackEventID, FeedbackPopData,
    FeedbackSendData, FeedbackPullData,
    FeedbackComCfg, FeedbackComExtra,

    )
from q1pulse.lang.flow_statements import (
        LoopDurationStatement,
        LoopBlock, ArrayLoopBlock,
        )
from q1pulse.lang.loops import Loop, LinspaceLoop, RangeLoop, ArrayLoop
from q1pulse.lang.math_expressions import Operand, Expression, Condition, RegisterCondition, ExpressionCondition
from q1pulse.lang.sequence import (
        Sequence, BlockStatement,
        IfBlockStatement, IfBranchSequence,
        )
from q1pulse.lang.simulator_statements import LogStatement
from q1pulse.lang.registers import Registers
from q1pulse.lang.register import Register
from q1pulse.lang.timed_statements import WaitRegStatement

logger = logging.getLogger(__name__)


class SequenceBuilder(BuilderBase):
    add_traceback_to_instructions = True
    '''
    Adding traceback is convenient to find a problem in your script.
    However, it makes the compiler pretty slow.
    Q1Instrument can suppress the traceback.
    '''

    MIN_DURATION = 4

    def __init__(self, name, isa_version):
        self.name = name
        self.isa_version = isa_version
        self._local_loop_cnt = 0
        self.Rs = Registers(self, local=True)
        self._sequence_stack = []
        self.sequence = None
        self._local_time = 0
        self._local_time_active = False
        self._compiled = False
        self._init_sequence = Sequence(None)
        self._conditional_block = None
        self._in_condition = False
        self._trigger_counters = []
        self._feedback_event_subscriptions: set[FeedbackEventID] = set()

    def start_sequence(self, program, timeline):
        self._timeline = timeline
        self._sequence_push(Sequence(self._timeline))

    def _sequence_push(self, sequence):
        self._sequence_stack.append(sequence)
        self.sequence = sequence

    def _sequence_pop(self):
        sequence = self._sequence_stack.pop()
        self.sequence = self._sequence_stack[-1]
        return sequence

    def _add_statement(self, statement, init_section=False):
        if SequenceBuilder.add_traceback_to_instructions and not isinstance(statement, str):
            self._add_traceback(statement)
        if self._compiled:
            raise Q1StateError('Program cannot be changed after compilation')
        if self.sequence.current_if_block is not None:
            self._close_if_block()
        if init_section:
            self._init_sequence.add(statement)
        else:
            self.sequence.add(statement)

    def _close_block(self, time: int):
        block = self._current_block
        block.close(time)
        self.sequence.has_timed_statements |= block.has_timed_statements

    @property
    def _current_block(self):
        block = self.sequence.last_statement
        if not isinstance(block, BlockStatement):
            raise Q1InternalError(f"Expected Block, but got {block}")
        return block

    def _add_traceback(self, statement):
        max_depth = 10
        # add 2 levels: _add_statement and _add_traceback.
        # these 2 levels are not added to statement.tb
        stack = traceback.extract_stack(limit=max_depth+2)
        tb = []
        tb.append('\nTraceback to Q1Pulse:\n')
        i = 0
        start = 0
        for entry in stack:
            i += 1
            # '<module>' is the root script (at least when running in Spyder)
            if entry.name == '<module>':
                start = i
        i = 0
        for entry in stack:
            i += 1
            if i < start:
                continue
            if i > max_depth:
                break
            tb.append(f'  File "{entry.filename}", line {entry.lineno}')
            tb.append(f'    {entry.line}\n')
        statement.tb = tb

    def wait(self, t):
        self.set_pulse_end(self.current_time + t)

    def add_comment(self, comment):
        self._add_statement(comment)

    def log(self, msg, var=None, time=False):
        '''
        Writes a value to the logging of Q1Simulator.
        It uses a special comment line in Q1ASM that is ignored by
        the Pulsar.
        '''
        self._add_statement(LogStatement(msg, var, time))

    def describe(self, fp=sys.stdout):
        init = []
        lines = []
        self._init_sequence.describe(init, init_section=True)
        self._sequence_stack[0].describe(lines)
        fp.write(f'Sequence:{self.name}\n')
        for line in init + lines:
            fp.write(line+'\n')
        fp.write('\n')

    def compile(self, generator):
        try:
            self._init_sequence.compile(generator)
            generator.start_main()
            self._sequence_stack[0].compile(generator)
            generator.end_main(self.end_time)
            self.modifies_frequency = generator.modifies_frequency
            subscribed_event_ids = self.subscribed_event_ids
            if subscribed_event_ids:
                generator.add_header_line(f"feedback event subscriptions: {subscribed_event_ids}")
            registers = generator.registers
            for name, reg in registers.items():
                generator.add_header_line(f"{reg}: {name}")
            self._compiled = True
        except Q1Exception as ex:
            logger.error(f'Compilation error on {self.name}', exc_info=True)
            msgs = [f'Error compiling {self.name}.']
            tb = []
            e = ex
            while e is not None:
                if isinstance(e, Q1SequenceError):
                    tb = e.traceback
                msgs.append(f'{type(e).__name__}: {e.args[0]}')
                e = e.__cause__
            q1_tb = '\n'.join(tb+msgs)
            self._dump_compile_state(generator, q1_tb, ex)
            # Use 'from None' to suppress original context
            # This avoids exposure of and confusion by q1pulse internals.
            raise Q1Exception(q1_tb) from None
        except Exception as ex:
            logger.error(f'Compilation error on {self.name}', exc_info=True)
            self._dump_compile_state(generator, None, ex)
            raise

    def _dump_compile_state(self, generator, q1_tb, exc):
        filename = os.path.join(os.getcwd(), '_q1pulse_dump.txt')
        print(f'**** Exception in {self.name} while compiling. ****')
        print(f'**** For details see: {filename} ****')
        with open(filename, 'w') as fp:
            fp.write(f'**** Exception in {self.name} while compiling. ****\n')
            if q1_tb:
                fp.write(q1_tb)
            fp.write('\n\n=== Q1Pulse Sequence ===\n')
            self.describe(fp)
            fp.write('\n=== Q1ASM till error ===\n')
            lines = generator.q1asm_lines()
            for line in lines:
                fp.write(line+'\n')
            fp.write('/-'*40 + '\n')
            fp.write('\n\n=== Full Exception ===\n\n')
            traceback.print_exception(exc, exc, None, file=fp)

    @property
    def current_time(self):
        return self.sequence.timeline.current_time + self._local_time

    def set_pulse_end(self, value):
        if self._local_time_active:
            self._local_time += max(0, value - self.current_time)
        else:
            self.sequence.timeline.set_pulse_end(value)

    @contextmanager
    def _local_timeline(self, duration=0, t_offset=0):
        if self._local_time_active:
            raise Q1InternalError('Local timeline already active')
        end_time = self.current_time + t_offset
        end_time += duration
        self._local_time = t_offset
        self._local_time_active = True
        yield
        if self.current_time > end_time:
            raise Q1TimingError(f"Local time exceeded specified end time: {self.current_time} > {end_time}")
        self._local_time = 0
        self._local_time_active = False
        self.set_pulse_end(end_time)

    @property
    def end_time(self):
        return self.sequence.timeline.end_time

    def enter_loop(self, loop):
        loop_sequence = Sequence(self._timeline)
        if isinstance(loop, (RangeLoop, LinspaceLoop)):
            loop_block = LoopBlock(self.end_time, loop)
        elif isinstance(loop, ArrayLoop):
            loop_block = ArrayLoopBlock(self.end_time, loop)
        else:
            raise Q1InternalError('Unknown loop')
        self._add_statement(loop_block)
        self._sequence_push(loop_sequence)

    def exit_loop(self, loop):
        end_time = self.end_time
        branch = self._sequence_pop()
        loop_block = self._current_block
        loop_block.add_branch(branch, end_time)
        self._close_block(end_time)

    @contextmanager
    def _seq_repeat(self, n):
        ''' repeat loop not synchronizing with other sequencers. '''
        if n == 0:
            raise ValueError('n must be > 0')
        if n == 1:
            yield
        else:
            t_start = self.current_time
            loop = Loop(self._local_loop_cnt, n, local=True)
            self._local_loop_cnt += 1
            loop_sequence = Sequence(self._timeline)
            loop_block = LoopBlock(t_start, loop)
            self._add_statement(loop_block)
            self._sequence_push(loop_sequence)

            yield

            t = self.current_time
            t_loop = t - t_start
            branch = self._sequence_pop()
            loop_block = self._current_block
            loop_block.add_branch(branch, t)
            self._close_block(t)
            # TODO: The LoopDurationStatement is a bit hacky.
            self._add_statement(LoopDurationStatement(n, t_loop))
            self.set_pulse_end(t_start + n * t_loop)

    def _add_reg_wait(self, reg):
        self._add_statement(WaitRegStatement(self.end_time, reg))

    @contextmanager
    def if_(self, condition: Operand):
        if self._conditional_block:
            raise Q1SyntaxError('If within rt-conditional is not supported')
        self.enter_if(condition)
        yield
        self.exit_if()

    @contextmanager
    def elif_(self, condition: Operand):
        self.enter_elif(condition)
        yield
        self.exit_elif()

    @property
    @contextmanager
    def else_(self):
        self.enter_else()
        yield
        self.exit_else()

    def enter_if(self, condition: Operand):
        self._start_if_block()
        self._add_if_branch(condition, "if")

    def exit_if(self):
        self._close_if_branch()

    def enter_elif(self, condition: Operand):
        if self.sequence.current_if_block is None:
            raise Q1SyntaxError("Cannot add `elif` without matching `if`")
        self._add_if_branch(condition, "elif")

    def exit_elif(self):
        self._close_if_branch()

    def enter_else(self):
        if self.sequence.current_if_block is None:
            raise Q1SyntaxError("Cannot add `else` without matching `if`")
        self._add_if_branch(None, "else")

    def exit_else(self):
        self._close_if_branch()
        self._close_if_block()

    def _start_if_block(self):
        if self.sequence.current_if_block is not None:
            self._close_if_block()

        if_block = IfBlockStatement(self.current_time)
        self._add_statement(if_block)
        self.sequence.current_if_block = if_block

    def _close_if_block(self):
        current_if_block = self.sequence.current_if_block
        if current_if_block is not None:
            self.sequence.current_if_block = None
            self._close_block(current_if_block.t_block_end)
            self.set_pulse_end(current_if_block.t_block_end)
            # @@@ set last timed statement for error check/report

    def _add_if_branch(self, condition: Operand, keyword: str):
        if isinstance(condition, Condition | NoneType):
            pass
        elif isinstance(condition, Register):
            condition = RegisterCondition(condition)
        elif isinstance(condition, Expression):
            condition = ExpressionCondition(condition)
        else:
            raise Q1SyntaxError(f"Cannot evaluate: {keyword} {condition}.")
        current_block = self.sequence.current_if_block
        timeline = copy(self._timeline)
        if_branch_sequence = IfBranchSequence(timeline, condition, keyword)
        # if_branch_sequence._last_timed_statement = current_block.last_timed_statement # @@@ Fix add to Branch
        self._sequence_push(if_branch_sequence)
        end_time = self.end_time
        # self.add_comment(f'branch start time: {end_time}')

    def _close_if_branch(self):
        end_time = self.end_time
        # self.add_comment(f'branch end time: {end_time}')
        branch = self._sequence_pop()
        self.sequence.current_if_block.add_branch(branch, end_time)

        # @@@ also set last timed statement (for time check and error messages..)
        end_time = self.end_time

    @property
    def trigger_counters(self):
        return self._trigger_counters

    def _add_trigger_counter(self, counter):
        self._trigger_counters.append(counter)

    def add_trigger_counter(self, trigger, threshold=1, invert=False):
        counter = TriggerCounter(trigger, threshold=threshold, invert=invert)
        self._add_trigger_counter(counter)
        return counter

    def latch_enable(self, enable, t_offset=0, wait_after=0):
        if enable not in [0, 1, True, False]:
            raise ValueError('Valid values for enable are 0, 1, True, False')
        time = self.current_time + t_offset
        self._add_statement(LatchEnableStatement(time, enable))
        self.set_pulse_end(time + wait_after)

    def latch_reset(self, t_offset=0, wait_after=0):
        time = self.current_time + t_offset
        self._add_statement(LatchResetStatement(time))
        self.set_pulse_end(time + wait_after)

    @contextmanager
    def conditional(self, counters, t_offset=0, evaluation_time=0):
        self.enter_conditional(counters, t_offset=t_offset, evaluation_time=evaluation_time)
        flags = CounterFlags(self)
        yield flags
        self.exit_conditional()

    def enter_conditional(self, counters, t_offset=0, evaluation_time=0):
        if self._conditional_block:
            raise Q1SyntaxError('Nested conditional is not supported')
        for counter in counters:
            if counter not in self._trigger_counters:
                raise Q1SyntaxError('Trigger counter {counter} not registered on sequencer')
        block = ConditionalBlockStatement(self.current_time+t_offset, counters)
        self._add_statement(block)
        self.set_pulse_end(self.current_time + t_offset + evaluation_time)
        self._conditional_block = block

    def exit_conditional(self):
        timeline = copy(self._timeline)
        self._conditional_block.close(timeline) # timeline to add else branch.
        self.set_pulse_end(self._conditional_block.end_time)
        self._conditional_block = None

    @contextmanager
    def condition(self, operator):
        self.enter_condition(operator)
        yield
        self.exit_condition()

    def enter_condition(self, operator):
        if self._conditional_block is None:
            raise Q1SyntaxError('Conditions must be wrapped in `conditional` section.')
        if self._in_condition:
            raise Q1SyntaxError('Conditions cannot be nested')
        self._in_condition = True
        timeline = copy(self._timeline)
        branch = BranchSequence(timeline, operator)
        self._sequence_push(branch)

    def exit_condition(self, end_time=None):
        if end_time is None:
            end_time = self.end_time
        self._conditional_block.set_end_time(end_time) # @@@ check for duplication icw add_branch.
        branch = self._sequence_pop()
        self._conditional_block.add_branch(branch, end_time)
        # self._last_timed_statement = self._conditional_block.last_timed_statement # @@@ TODO
        self._in_condition = False

    @property
    def subscribed_event_ids(self) -> list[int]:
        return [fb.event_id for fb in self._feedback_event_subscriptions]

    def fb_subscribe(self, event_id: FeedbackEventID):
        """Subscribes to event_id to make it available for `fb_pull_data`.
        """
        self._feedback_event_subscriptions.add(event_id)

    def fb_pop_data(self, event_id: FeedbackEventID, register: Register):
        # automatic registration of event.
        self._feedback_event_subscriptions.add(event_id)
        self._add_statement(FeedbackPopData(event_id, register))

    def fb_pull_data(self, event_id_destination: Register, register: Register):
        self._add_statement(FeedbackPullData(event_id_destination, register))

    def fb_com_data(self, event_id: FeedbackEventID, value: Operand, t_offset: int = 0, wait_after: int = 0):
        time = self.current_time + t_offset
        self._add_statement(FeedbackSendData(time, event_id, value))
        self.set_pulse_end(time + wait_after)

    def fb_com_cfg(self, write_combine: bool, shift: int, n_bytes: int, t_offset: int = 0, wait_after: int = 0):
        """
        Args:
            write_combine: if True enable write combine.
            shift: left shift
            n_bytes: total number of bytes of combined message.
        """
        time = self.current_time + t_offset
        self._add_statement(FeedbackComCfg(time, write_combine, shift, n_bytes))
        self.set_pulse_end(time + wait_after)

    def fb_com_extra(self, valid: bool, extra: int, t_offset: int = 0, wait_after: int = 0):
        time = self.current_time + t_offset
        self._add_statement(FeedbackComExtra(time, valid, extra))
        self.set_pulse_end(time + wait_after)
