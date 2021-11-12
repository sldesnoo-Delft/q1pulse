from contextlib import contextmanager

from .builderbase import BuilderBase
from .registers import Registers
from .timed_statements import TimedStatement, SyncTimeStatement, WaitRegStatement
from .flow_statements import (
        BranchStatement,
        LoopStatement, EndLoopStatement,
        LinspaceLoopStatement, EndLinspaceLoopStatement,
        RepeatStatement, EndRepeatStatement,
        )
from .loops import LinspaceLoop, RangeLoop, loopable
from .sequencer_data import WaveCollection, AcquisitionSections

class SequenceBuilder(BuilderBase):
    def __init__(self, name):
        self.name = name
        self._local_loop_cnt = 0
        self.Rs = Registers(self, local=True)
        self._waves = WaveCollection()
        self._acquisitions = AcquisitionSections()
        self._sequence_stack = []
        self._local_time = 0
        self._local_time_active = False

    def start_sequence(self, program, timeline):
        self._program = program
        self._timeline = timeline
        self._start_sequence()

    def add_wave(self, name, data):
        return self._waves.add_wave(name, data)

    def add_acquisition(self, name, num_bins):
        return self._acquisitions.add_section(name, num_bins)

    def _start_sequence(self):
        self._sequence_stack.append(Sequence(self._timeline))

    @property
    def sequence(self):
        return self._sequence_stack[-1]

    def _add_statement(self, statement):
        self.sequence.add(statement)

    def wait(self, t):
        if self._local_time_active:
            self._local_time += t
        else:
            self.set_pulse_end(self.current_time + t)

    def add_comment(self, comment):
        self._add_statement(comment)

    def describe(self):
        init_section = []
        lines = []
        self._sequence_stack[0].describe(init_section, lines, indent=0)
        print(f'Sequence:{self.name}')
        for line in init_section + lines:
            print(line)
        print()

    def compile(self, generator, annotate=False):
        self._sequence_stack[0].compile(generator, annotate)

    @property
    def current_time(self):
        return self.sequence.timeline.current_time + self._local_time

    def set_pulse_end(self, value):
        self.sequence.timeline.set_pulse_end(value)


    @contextmanager
    def _local_timeline(self, duration=None, t_offset=0):
        self._local_time = t_offset
        self._local_time_active = True
        yield
        self.set_pulse_end(self.current_time)
        self._local_time = 0
        self._local_time_active = False

    @property
    def end_time(self):
        return self.sequence.timeline.end_time

    def enter_loop(self, label, loop):
        self._add_statement(SyncTimeStatement(self.sequence.timeline.end_time))
        loop_sequence = Sequence(self._timeline)
        if isinstance(loop, RangeLoop):
            loop_registers = [self.Rs.add_reg(name) for name in loop.reg_names()]
            loop_statement = LoopStatement(loop_sequence, label, loop_registers, loop)
            loop_sequence.exit_statement = EndLoopStatement(label, loop_registers, loop)
        elif isinstance(loop, LinspaceLoop):
            loop_registers = [self.Rs.add_reg(name) for name in loop.reg_names()]
            loop_statement = LinspaceLoopStatement(loop_sequence, label, loop_registers, loop)
            loop_sequence.exit_statement = EndLinspaceLoopStatement(label, loop_registers, loop)
        else:
            raise Exception('Unknown loop')
        self._add_statement(loop_statement)
        self._sequence_stack.append(loop_sequence)

    def exit_loop(self):
        self._add_statement(SyncTimeStatement(self.sequence.timeline.end_time))
        self.sequence.close()
        self._sequence_stack.pop()

    @contextmanager
    def _seq_repeat(self, n):
        ''' repeat loop not synchronizing with other sequencers. Internal use only '''
        if n == 0:
            return
        if n == 1:
            yield
        else:
            label = f'local_{self._local_loop_cnt}'
            reg_name = f'_cnt{self._local_loop_cnt}'
            self._local_loop_cnt += 1
            loop_register = self.Rs.add_reg(reg_name)
            loop_sequence = Sequence(self._timeline)
            loop_statement = RepeatStatement(loop_sequence, label, loop_register, n)
            loop_sequence.exit_statement = EndRepeatStatement(label, loop_register)
            self._add_statement(loop_statement)
            self._sequence_stack.append(loop_sequence)

            yield

            self.sequence.close()
            self._sequence_stack.pop()

    @loopable
    def _add_reg_wait(self, reg):
        self._add_statement(WaitRegStatement(self.sequence.timeline.end_time, reg))


class Sequence:
    def __init__(self, timeline):
        self.timeline = timeline
        self._statements = []
        self.exit_statement = None

    def close(self):
        if self.exit_statement is not None:
            self.add(self.exit_statement)

    def add(self, statement):
        self._statements.append(statement)

    def describe(self, init_section, lines, indent=0):
        white = '    ' * indent
        for statement in self._statements:
            statement_str = str(statement)
            if statement_str == 'endloop':
                continue
            if isinstance(statement, TimedStatement):
                time = f'{statement.time:6}'
            else:
                time = ' '*6
            if getattr(statement, 'init_section', False):
                line = f'-init-  {statement}'
                init_section.append(line)
            else:
                line = f'{time}  {white}{statement}'
                lines.append(line)
            if isinstance(statement, BranchStatement):
                statement.sequence.describe(init_section, lines, indent+1)

    def compile(self, generator, annotate=False):
        for statement in self._statements:
            if annotate:
                s = str(statement)
                if isinstance(statement, TimedStatement):
                    s += f' t={statement.time}'
                init_section = getattr(statement, 'init_section', False)
                generator.add_comment(s, init_section)
            if isinstance(statement, str):
                if not annotate:
                    generator.add_comment(statement)
                continue
            statement.write_instruction(generator)
            if isinstance(statement, BranchStatement):
                with generator.scope():
                    statement.sequence.compile(generator, annotate)
# TODO: @@@ Replace with contextmanager and add end statement to BranchStatement.
#                    with statement.branch() as sequence: # @@@ Use contextmanager
#                        sequence.compile(generator, annotate)
