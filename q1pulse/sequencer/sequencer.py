import sys
import os
from copy import copy
from contextlib import contextmanager
import traceback
import logging

from .builderbase import BuilderBase
from q1pulse.lang.triggers import TriggerCounter
from q1pulse.lang.exceptions import (
        Q1StateError, Q1Exception,
        Q1InternalError, Q1SequenceError,
        Q1TimingError, Q1SyntaxError,
        )
from q1pulse.lang.sequence import Sequence
from q1pulse.lang.loops import Loop
from q1pulse.lang.math_expressions import Operand
from q1pulse.lang.registers import Registers
from q1pulse.lang.register import Register
from q1pulse.lang.timed_statements import WaitRegStatement, TimedStatement
from q1pulse.lang.flow_statements import (
        LoopDurationStatement,
        LoopStatement, EndLoopStatement,
        ArrayLoopStatement, EndArrayLoopStatement,
        )
from q1pulse.lang.loops import LinspaceLoop, RangeLoop, ArrayLoop
from q1pulse.lang.simulator_statements import LogStatement
from q1pulse.lang.conditions import (
        LatchEnableStatement, LatchResetStatement,
        BranchSequence, ConditionalBlockStatement,
        CounterFlags,
        )
from q1pulse.lang.feedback import (
    FeedbackEventID, FeedbackPopData,
    FeedbackSendData, FeedbackPullData,
    FeedbackComCfg, FeedbackComExtra,

    )

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
        self._last_timed_statement = None
        self._conditional_block = None
        self._in_condition = False
        self._trigger_counters = []
        self._feedback_event_subscriptions: set[FeedbackEventID] = set()

    def start_sequence(self, program, timeline):
        self._program = program
        self._timeline = timeline
        self._sequence_push(Sequence(self._timeline))

    def _sequence_push(self, sequence):
        self._sequence_stack.append(sequence)
        self.sequence = sequence

    def _sequence_pop(self):
        self._sequence_stack.pop()
        self.sequence = self._sequence_stack[-1]

    def _add_statement(self, statement, init_section=False):
        self._check_time(statement)
        if SequenceBuilder.add_traceback_to_instructions and not isinstance(statement, str):
            self._add_traceback(statement)
        if self._compiled:
            raise Q1StateError('Program cannot be changed after compilation')
        if init_section:
            self._init_sequence.add(statement)
        else:
            self.sequence.add(statement)

    def _check_time(self, statement):
        # TODO: Distinguish parameter operations vs RT IO / RT control instructions.
        if not isinstance(statement, TimedStatement):
            return
        t = statement.time
        last = self._last_timed_statement
        if last and t != last.time:
            delta_t = t - last.time
            if delta_t < 0:
                raise Q1TimingError(f'Statement time cannot be before {last.time}\n'
                                    f'Previous: t={last.time}  {last}\n'
                                    f'Adding:   t={statement.time}  {statement}')
            if delta_t < SequenceBuilder.MIN_DURATION:
                raise Q1TimingError(f'Time between statements must be at least of 4 ns:\n'
                                    f'Adding:  t={statement.time}  {statement} (delta_t {delta_t})')
        self._last_timed_statement = statement

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

    def compile(self, generator, annotate=False):
        try:
            self._init_sequence.compile(generator, annotate)
            generator.start_main()
            self._sequence_stack[0].compile(generator, annotate)
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
        self._local_time = 0
        self._local_time_active = False
        self.set_pulse_end(end_time)

    @property
    def end_time(self):
        return self.sequence.timeline.end_time

    def enter_loop(self, loop):
        loop_sequence = Sequence(self._timeline)
        if isinstance(loop, (RangeLoop, LinspaceLoop)):
            loop_statement = LoopStatement(self.end_time, loop_sequence, loop)
        elif isinstance(loop, ArrayLoop):
            loop_statement = ArrayLoopStatement(self.end_time, loop_sequence, loop)
        else:
            raise Q1InternalError('Unknown loop')
        self._add_statement(loop_statement)
        self._sequence_push(loop_sequence)

    def exit_loop(self, loop):
        if isinstance(loop, (RangeLoop, LinspaceLoop)):
            loop_end_statement = EndLoopStatement(self.end_time, loop)
        elif isinstance(loop, ArrayLoop):
            loop_end_statement = EndArrayLoopStatement(self.end_time, loop)
        else:
            raise Q1InternalError('Unknown loop')
        self._add_statement(loop_end_statement)
        self._sequence_pop()

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
            loop_statement = LoopStatement(self.current_time, loop_sequence, loop)
            self._add_statement(loop_statement)
            self._sequence_push(loop_sequence)

            yield

            loop_end_statement = EndLoopStatement(self.current_time, loop)
            self._add_statement(loop_end_statement)
            t_loop = self.current_time - t_start
            self._add_statement(LoopDurationStatement(n, t_loop))
            self._sequence_pop()
            self.set_pulse_end(t_start + n * t_loop)

    def _add_reg_wait(self, reg):
        self._add_statement(WaitRegStatement(self.end_time, reg))

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
        self._conditional_block.close(timeline)
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
        self._conditional_block.add_branch(branch)
        self._sequence_push(branch)

    def exit_condition(self, end_time=None):
        if end_time is None:
            end_time = self.end_time
        self.add_comment(f'Condition end time: {end_time}')
        self._conditional_block.set_end_time(end_time)
        self._in_condition = False
        self._sequence_pop()
        self._last_timed_statement = self._conditional_block

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
