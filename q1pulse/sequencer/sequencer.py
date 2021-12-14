import sys
import os
from contextlib import contextmanager
import traceback

from .builderbase import BuilderBase
from ..lang.exceptions import (
        Q1StateError, Q1Exception,
        Q1InternalError, Q1SequenceError,
        Q1TimingError
        )
from ..lang.sequence import Sequence
from ..lang.loops import Loop
from ..lang.registers import Registers
from ..lang.timed_statements import WaitRegStatement, TimedStatement
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
        self._last_timed_statement = None

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
        self._check_time(statement)
        if not isinstance(statement, str):
            self._add_traceback(statement)
        if self._compiled:
            raise Q1StateError('Program cannot be changed after compilation')
        if init_section:
            self._init_sequence.add(statement)
        else:
            self.sequence.add(statement)

    def _check_time(self, statement):
        if not isinstance(statement, TimedStatement):
            return
        t = statement.time
        if int(t) % 4:
            raise Q1TimingError(f'Time must be multiple of 4 ns:\n'
                                f'Adding:  t={statement.time}  {statement}')
        last = self._last_timed_statement
        if last and t < last.time:
            raise Q1TimingError(f'Statement time cannot be before {last.time}\n'
                                f'Previous: t={last.time}  {last}\n'
                                f'Adding:   t={statement.time}  {statement}')
        self._last_timed_statement = statement

    def _add_traceback(self, statement):
        max_depth=10
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
        q1exception = None
        try:
            if not self._compiled:
                self._compiled = True
            self._init_sequence.compile(generator, annotate)
            generator.start_main()
            self._sequence_stack[0].compile(generator, annotate)
            generator.end_main(self.end_time)
        except Q1Exception as ex:
            msgs = [f'Error compiling {self.name}.']
            tb = []
            e = ex
            while e is not None:
                if isinstance(e, Q1SequenceError):
                    tb = e.traceback
                msgs.append(f'{type(e).__name__}: {e.args[0]}')
                e = e.__cause__
            q1_tb = '\n'.join(tb+msgs)
            q1exception = Q1Exception(q1_tb)
            self._dump_compile_state(generator, q1_tb, ex)
        except Exception as ex:
            self._dump_compile_state(generator, None, ex)
        # Raise exception after handler
        # This avoids exposure of / confusion by q1pulse internals.
        if q1exception:
            raise q1exception

    def _dump_compile_state(self, generator, q1_tb, exc):
        filename = os.path.join(os.getcwd(), '_q1pulse_dump.txt')
        print(f'**** Exception in {self.name} while compiling. ****')
        print(f'**** For details see: {filename} ****')
        with open(filename, 'w') as fp:
            fp.write(f'**** Exception in {self.name} while compiling. ****\n')
            if q1_tb:
                fp.write(q1_tb)
            fp.write(f'\n\n=== Q1Pulse Sequence ===\n')
            self.describe(fp)
            fp.write(f'\n=== Q1ASM till error ===\n')
            lines = generator.q1asm_lines()
            for line in lines:
                fp.write(line+'\n')
            fp.write('/-'*40 + '\n')
            fp.write(f'\n\n=== Full Exception ===\n\n')
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
            raise Q1InternalError('Unknown loop')
        self._add_statement(loop_statement)
        self._sequence_stack.append(loop_sequence)

    def exit_loop(self, loop):
        if isinstance(loop, (RangeLoop, LinspaceLoop)):
            loop_end_statement = EndLoopStatement(self.end_time, loop)
        elif isinstance(loop, ArrayLoop):
            loop_end_statement = EndArrayLoopStatement(self.end_time, loop)
        else:
            raise Q1InternalError('Unknown loop')
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

