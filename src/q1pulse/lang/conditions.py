from enum import IntEnum
from contextlib import contextmanager

from .timed_statements import TimedStatement
from .sequence import Sequence, BlockStatement
from .exceptions import Q1InternalError, Q1SyntaxError


class Operators(IntEnum):
    OR = 0
    """ At least 1 bit set """
    NOR = 1
    """ No bit set """
    AND = 2
    """ All bits set """
    NAND = 3
    """ Not all bits set """
    XOR = 4
    """ Odd number of bits set """
    XNOR = 5
    """ Even number of bits set """

    @property
    def family(self):
        return Operators(self & 0b110)

    @property
    def opposite(self):
        return Operators(self ^ 0b001)


class CounterFlags():
    def __init__(self, parent):
        self.parent = parent

    @contextmanager
    def at_least_one_set(self):
        with self.parent.condition(Operators.OR):
            yield

    @contextmanager
    def none_set(self):
        with self.parent.condition(Operators.NOR):
            yield

    @contextmanager
    def all_set(self):
        with self.parent.condition(Operators.AND):
            yield

    @contextmanager
    def not_all_set(self):
        with self.parent.condition(Operators.NAND):
            yield

    @contextmanager
    def odd(self):
        with self.parent.condition(Operators.XOR):
            yield

    @contextmanager
    def even(self):
        with self.parent.condition(Operators.XNOR):
            yield


class LatchEnableStatement(TimedStatement):
    def __init__(self, time, enable):
        super().__init__(time)
        self.enable = enable

    def __repr__(self):
        return f"latch_enable({self.enable})"

    def write_instruction(self, generator):
        generator.set_latch_en(self.time, int(self.enable))


class LatchResetStatement(TimedStatement):
    def __init__(self, time):
        super().__init__(time)

    def __repr__(self):
        return "latch_reset()"

    def write_instruction(self, generator):
        generator.latch_rst(self.time)


class BranchSequence(Sequence):
    def __init__(self, timeline, operator):
        super().__init__(timeline)
        self.operator = operator
        self.set_header(f"condition({self.operator.name}):")


class ConditionalBlockStatement(BlockStatement):

    """
    Statement containing one or more conditions on a set of trigger counters.

    The duration of the conditional block is fixed.
    Wait times are added at the end of every branch to enforce equal duration.

    Some time is needed between the conditional block statement and the
    first statement of any else-branch, because it takes time to skip the
    statements of the previous branches.
    Some time is also needed to skip the statements of subsequent branches.
    This could result in some additional execution time for the block.

    Branches are added in programming order.
    """

    def __init__(self, time, counters):
        super().__init__(time)
        self.counters = counters
        self._closed = False

    def add_branch(self, branch_sequence, end_time):
        operator = branch_sequence.operator
        if operator in [branch.operator for branch in self.branches]:
            raise Q1SyntaxError(f"Duplicate operator {operator.name}")
        super().add_branch(branch_sequence, end_time)
        self._check_operators()

    @property
    def end_time(self):
        return self.t_block_end

    def close(self, timeline):
        """
        Adds else branch of equal length.
        get first RT statement and last RT statement
        """
        else_operator = self._get_else()
        if else_operator is not None:
            self.add_branch(BranchSequence(timeline, else_operator), self.t_block_start)
        self._closed = True

    def _check_operators(self):
        # _get_else raises an exception when branches are not exclusive.
        self._get_else()

    def _get_else(self):
        tri_state = set([Operators.AND, Operators.NOR, Operators.XOR])
        operators = [branch.operator for branch in self.branches]
        if len(operators) == 1:
            return operators[0].opposite
        if len(self.counters) == 1:
            if len(operators) > 2:
                raise Q1SyntaxError("Cannot have more than 2 different operators with 1 counter")
            flag_set_ops = [Operators.AND, Operators.OR, Operators.XOR]
            if (operators[0] in flag_set_ops) == (operators[1] in flag_set_ops):
                raise Q1SyntaxError(f"Incompatible operators {[op.name for op in operators]} on 1 counter")
            return None
        if len(operators) == 2:
            if operators[0].family == operators[1].family:
                # all options already covered
                return None
            try:
                for op in operators:
                    tri_state.remove(op)
                return list(tri_state)[0]
            except KeyError:
                raise Q1SyntaxError(f"Operators {[op.name for op in operators]} are not exclusive") from None
        else:
            try:
                for op in operators:
                    tri_state.remove(op)
                return None
            except KeyError:
                raise Q1SyntaxError(f"Operators {[op.name for op in operators]} are not exclusive") from None

    def __repr__(self):
        return (
            f"conditional({[counter.name for counter in self.counters]}) {self.t_block_start} ... {self.t_block_end}:"
            )

    def write_instruction(self, generator):
        if not self._closed:
            raise Q1InternalError("Condition not closed")

        mask = 0
        for counter in self.counters:
            mask |= 1 << (counter.address-1)

        with generator.scope():
            if self.has_timed_statements:
                # TODO: start/end can shift to match 4 ns constraint.

                # includes call to rt_seq_end()
                generator.enter_conditional(self.t_block_start)

                for branch in self.branches:
                    # includes call to rt_seq_start()
                    generator.set_condition(mask, branch.operator)
                    branch.compile(generator)
                    # includes call to rt_seq_flush()
                    generator.exit_condition()

                # includes call to rt_seq_start()
                generator.exit_conditional(self.t_block_end)
            else:
                # on sequencer wihout timed instructions.
                # Branches Should be empty! Raise error if branch not empty?
                for branch in self.branches:
                    branch.compile(generator)
