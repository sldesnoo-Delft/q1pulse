from .sequence import Sequence
from .timed_statements import MultiBranchStatement


class IfBranchSequence(Sequence):
    def __init__(self, timeline, condition, keyword: str):
        super().__init__(timeline)
        self.condition = condition
        self.keyword = keyword

    def describe(self, lines, indent=0, init_section=False):
        white = '    ' * indent
        time = ' '*6
        line = f'{time}{white}{self.keyword} {self.condition}:'
        lines.append(line)
        super().describe(lines, indent=indent, init_section=init_section)


class IfBlockStatement(MultiBranchStatement):
    '''
    Statement containing one or more if/elif conditions closed by an else statement.

    The duration of the conditional block is fixed.
    Wait times are added at the end of every branch to enforce equal duration.
    '''

    def __init__(self, time, last_timed_statement):
        super().__init__(time)
        self._closed = False
        self._end_time = time
        self.last_timed_statement = last_timed_statement

    def add_branch(self, branch_sequence: IfBranchSequence):
        self.branches.append(branch_sequence)

    @property
    def end_time(self):
        return self._end_time

    def set_end_time(self, value):
        self._end_time = max(self._end_time, value)

    def close(self):
        self._closed = True

    def __repr__(self):
        return '# if-block'

    def write_instruction(self, generator):
        # set if-else end label enforces equal end-time.
        generator.enter_if_block(self.time, self.end_time)
        n = len(self.branches)
        for i, branch in enumerate(self.branches):
            last = i == n-1
            generator.enter_if_branch(branch.condition, last=last)
            branch.compile(generator, annotate=False)
            generator.exit_if_branch(last=last)
        generator.exit_if_block()
