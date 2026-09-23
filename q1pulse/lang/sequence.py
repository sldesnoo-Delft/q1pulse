from __future__ import annotations
from abc import abstractmethod
from .base import Statement
from .exceptions import Q1Exception, Q1SequenceError, Q1TimingError
from .timed_statements import TimedStatement


class Sequence:
    MIN_DURATION = 4

    def __init__(self, timeline):
        self.timeline = timeline
        self._statements = []
        self._last_timed_statement = None # TODO get from parent... last_timed_statement
        self.has_timed_statements = False
        self._if_block: IfBlockStatement | None = None # current if block or current block?
        self._header: str | None = None

    def add(self, statement: Statement):
        self._check_time(statement)
        self._statements.append(statement)

    @property
    def last_statement(self):
        return self._statements[-1]

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
            if delta_t < Sequence.MIN_DURATION:
                raise Q1TimingError(f'Time between statements must be at least of 4 ns:\n'
                                    f'Previous: t={last.time}  {last}\n'
                                    f'Adding:  t={statement.time}  {statement} (delta_t {delta_t})')
        self._last_timed_statement = statement
        self.has_timed_statements = True

    @property
    def time_last_timed_statement(self):
        return self._last_timed_statement.time

    @property
    def current_if_block(self):
        return self._if_block

    @current_if_block.setter
    def current_if_block(self, if_block):
        self._if_block = if_block

    def _close_if_block(self, auto: bool = False):
        if self._if_block is not None:
            self._if_block.close()
            self._if_block = None
            self._if_auto_closed = auto

    def set_header(self, header: str):
        self._header = header

    def describe(self, lines, indent=0, init_section=False):
        white = '    ' * indent
        if self._header:
            lines.append('#     ' + white + self._header)
        for statement in self._statements:
            is_comment = isinstance(statement, str)
            statement_str = str(statement)
            if statement_str == 'endloop':
                continue
            if isinstance(statement, TimedStatement):
                time = f'{statement.time:6}'
            elif init_section:
                time = '-init-'
            elif is_comment:
                time = '#     '
            else:
                time = ' '*6
            line = f'{time}  {white}{statement}'
            lines.append(line)
            if isinstance(statement, BlockStatement):
                for branch in statement.branches:
                    branch.describe(lines, indent+1)

    def compile(self, generator):
        try:
            for statement in self._statements:
                if isinstance(statement, str):
                    generator.add_comment(statement)
                    continue
                if generator.annotate:
                    s = str(statement)
                    if isinstance(statement, TimedStatement):
                        s += f' t={statement.time}'
                    generator.add_comment(s)
                statement.write_instruction(generator)
        except Q1SequenceError:
            raise
        except Q1Exception as ex:
            tb = getattr(statement, 'tb', [])
            raise Q1SequenceError(f'on statement\n    [Q1Pulse]   {statement}', tb) from ex
        except Exception as ex:
            raise Exception(f'Error on statement {statement}') from ex


class BlockStatement(Statement):

    # TODO Count Timed instructions: start and end of sequence...

    def __init__(self, time):
        self.t_block_start = time
        self.t_block_end = time
        self.has_timed_statements = False
        self.branches: list[Sequence] = []

    def add_branch(self, sequence: Sequence, end_time: int):
        self.branches.append(sequence)
        self.has_timed_statements |= sequence.has_timed_statements
        # TODO also set last timed statement for proper check on sequence timing...
        self.t_block_end = max(self.t_block_end, end_time)

    def set_end_time(self, time):
        self.t_block_end = max(self.t_block_end, time)

    def close(self, time):
        if time > self.t_block_end:
            raise Q1TimingError(f"A branch exceeds duration of block: {self.t_block_end} > {time}")
        self.t_block_end = time

    def write_instruction(self, generator):
        ...


class IfBranchSequence(Sequence):
    def __init__(self, timeline,
                 condition,
                 keyword: str):
        super().__init__(timeline)
        self.condition = condition
        self.keyword = keyword
        self.set_header(f"{self.keyword} {self.condition}:")


class IfBlockStatement(BlockStatement):

    # TODO SOFT ALIGN !
    # TODO: start/end can shift to match 4 ns constraint.
    # IF not all first RT statements at same time, then find minimum (0 or 4)
    #    could also be 5, 6 or 7 for perfect match with previous statement.
    # End time could also be adjusted the same way.

    def __repr__(self):
        return '# if-block'

    def write_instruction(self, generator):
        with generator.scope():
            end_label = generator.generate_label("endif")
            n_branches = len(self.branches)
            if self.has_timed_statements:
                # TODO: Pending update at rt_seq_start might not be needed
                #       It may collide with non-updating RT instruction.

                generator.rt_seq_end(self.t_block_start)
                generator.add_comment(f"if-block {self.t_block_start}, {self.t_block_end}")

                for i, branch in enumerate(self.branches):
                    condition = branch.condition
                    last = i == n_branches-1
                    generator.add_comment(f"condition {condition}")
                    continue_label = generator.generate_label("cont")
                    if condition is not None:
                        # Note: condition is None for else branch
                        condition.test(generator)
                        label = end_label if last else continue_label
                        generator.cnjmp(condition.comparison_operator, "@"+label)
                    generator.rt_seq_start(self.t_block_start)
                    branch.compile(generator)
                    generator.rt_seq_end(self.t_block_end)
                    generator.rt_clear_pending_update()
                    if not last:
                        generator.jmp("@"+end_label)
                        generator.set_label(continue_label)

                generator.set_label(end_label)
                generator.rt_seq_start(self.t_block_end)
            else:
                for i, branch in enumerate(self.branches):
                    condition = branch.condition
                    last = i == n_branches-1
                    generator.add_comment(f"condition {condition}")
                    continue_label = generator.generate_label("cont")
                    if condition is not None:
                        # Note: condition is None for else branch
                        condition.test(generator)
                        label = end_label if last else continue_label
                        generator.cnjmp(condition.comparison_operator, "@"+label)
                    branch.compile(generator)
                    if not last:
                        generator.jmp("@"+end_label)
                        generator.set_label(continue_label)

                generator.set_label(end_label)
