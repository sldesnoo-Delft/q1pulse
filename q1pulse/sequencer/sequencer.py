from contextlib import contextmanager

from .builderbase import BuilderBase
from ..lang.sequence import Sequence
from ..lang.loops import Loop
from ..lang.registers import Registers
from ..lang.timed_statements import WaitRegStatement
from ..lang.flow_statements import (
        LoopDurationStatement,
        LoopStatement, EndLoopStatement,
        ArrayLoopStatement, EndArrayLoopStatement,
        )
from ..lang.loops import LinspaceLoop, RangeLoop, ArrayLoop
from ..lang.simulator_statements import LogStatement

class SequenceBuilder(BuilderBase):
    def __init__(self, name):
        self.name = name
        self._local_loop_cnt = 0
        self.Rs = Registers(self, local=True)
        self._sequence_stack = []
        self._local_time = 0
        self._local_time_active = False
        self._compiled = False
        self._init_sequence = Sequence(None)

    def start_sequence(self, program, timeline):
        self._program = program
        self._timeline = timeline
        self._start_sequence()

    def _start_sequence(self):
        self._sequence_stack.append(Sequence(self._timeline))

    @property
    def sequence(self):
        return self._sequence_stack[-1]

    def _add_statement(self, statement, init_section=False):
        if self._compiled:
            raise Exception('Program cannot be changed after compilation')
        if init_section:
            self._init_sequence.add(statement)
        else:
            self.sequence.add(statement)

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

    def describe(self):
        init = []
        lines = []
        self._init_sequence.describe(init, init_section=True)
        self._sequence_stack[0].describe(lines)
        print(f'Sequence:{self.name}')
        for line in init + lines:
            print(line)
        print()

    def compile(self, generator, annotate=False):
        try:
            if not self._compiled:
                self._compiled = True
            self._init_sequence.compile(generator, annotate)
            generator.start_main()
            self._sequence_stack[0].compile(generator, annotate)
            generator.end_main(self.end_time)
        except:
            print(f'Exception in {self.name} while compiling:')
            lines = generator.q1asm_lines()
            for line in lines:
                print(line)
            raise

    @property
    def current_time(self):
        return self.sequence.timeline.current_time + self._local_time

    def set_pulse_end(self, value):
        if self._local_time_active:
            self._local_time += max(0, value - self.current_time)
        else:
            self.sequence.timeline.set_pulse_end(value)


    @contextmanager
    def _local_timeline(self, duration=None, t_offset=0):
        end_time = self.current_time + t_offset
        if duration is not None:
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
            raise Exception('Unknown loop')
        self._add_statement(loop_statement)
        self._sequence_stack.append(loop_sequence)

    def exit_loop(self, loop):
        if isinstance(loop, (RangeLoop, LinspaceLoop)):
            loop_end_statement = EndLoopStatement(self.end_time, loop)
        elif isinstance(loop, ArrayLoop):
            loop_end_statement = EndArrayLoopStatement(self.end_time, loop)
        else:
            raise Exception('Unknown loop')
        self._add_statement(loop_end_statement)
        self._sequence_stack.pop()

    @contextmanager
    def _seq_repeat(self, n):
        ''' repeat loop not synchronizing with other sequencers. Internal use only ''' # @@@ looks like it can be used normally
        if n == 0:
            return
        if n == 1:
            yield
        else:
            t_start = self.current_time
            loop = Loop(self._local_loop_cnt, n, local=True)
            self._local_loop_cnt += 1
            loop_sequence = Sequence(self._timeline)
            loop_statement = LoopStatement(self.current_time, loop_sequence, loop)
            self._add_statement(loop_statement)
            self._sequence_stack.append(loop_sequence)

            yield

            loop_end_statement = EndLoopStatement(self.current_time, loop)
            self._add_statement(loop_end_statement)
            t_loop = self.current_time - t_start
            self._add_statement(LoopDurationStatement(n, t_loop))
            self._sequence_stack.pop()
            self.set_pulse_end(t_start + n * t_loop)


    def _add_reg_wait(self, reg):
        self._add_statement(WaitRegStatement(self.sequence.timeline.end_time, reg))

