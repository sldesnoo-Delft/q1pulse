from .timed_statements import TimedStatement
from .flow_statements import BranchStatement

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

    def describe(self, lines, indent=0, init_section=False):
        white = '    ' * indent
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
            if isinstance(statement, BranchStatement):
                statement.sequence.describe(lines, indent+1)

    def compile(self, generator, annotate=False):
        for statement in self._statements:
            if annotate:
                s = str(statement)
                if isinstance(statement, TimedStatement):
                    s += f' t={statement.time}'
                generator.add_comment(s)
            if isinstance(statement, str):
                if not annotate:
                    generator.add_comment(statement)
                continue
            try:
                statement.write_instruction(generator)
            except Exception as ex:
                raise Exception(f'Compilation error on statement {statement}') from ex
            if isinstance(statement, BranchStatement):
                with generator.scope():
                    statement.sequence.compile(generator, annotate)

# TODO: @@@ Replace with contextmanager and add end statement to BranchStatement.
#                    with statement.branch() as sequence: # @@@ Use contextmanager
#                        sequence.compile(generator, annotate)
