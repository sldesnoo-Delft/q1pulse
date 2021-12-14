from .timed_statements import TimedStatement
from .flow_statements import BranchStatement
from .exceptions import Q1Exception, Q1SequenceError

class Sequence:
    def __init__(self, timeline):
        self.timeline = timeline
        self._statements = []

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
                if not isinstance(statement, BranchStatement):
                    statement.write_instruction(generator)
                else:
                    with generator.scope():
                        generator.block_end()
                        statement.write_instruction(generator)
                        generator.block_start()
                        statement.sequence.compile(generator, annotate)
                        generator.block_end()
                        generator.block_start()
            except Q1SequenceError:
                raise
            except Q1Exception as ex:
                tb = getattr(statement, 'tb', [])
                raise Q1SequenceError(f'on statement\n    [Q1Pulse]   {statement}', tb) from ex
            except Exception as ex:
                raise Exception(f'Error on statement {statement}') from ex
