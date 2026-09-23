from __future__ import annotations
from abc import abstractmethod, ABC
from enum import Enum

import numpy as np

from .exceptions import Q1TypeError


class Operand(ABC):

    @property
    @abstractmethod
    def dtype(self):
        pass

    def __add__(self, rhs):
        return Addition(self, rhs)

    def __radd__(self, lhs):
        return Addition(lhs, self)

    def __sub__(self, rhs):
        return Subtraction(self, rhs)

    def __rsub__(self, lhs):
        return Subtraction(lhs, self)

    def __neg__(self):
        if self.dtype == int:
            return Subtraction(0, self)
        if self.dtype == float:
            return Subtraction(0.0, self)
        return NotImplemented

    def __mul__(self, lhs):
        return Multiply(self, lhs)

    def __rmul__(self, rhs):
        return Multiply(rhs, self)

    def lsr(self, rhs):
        return Lsr(self, rhs)

    def __lshift__(self, rhs):
        return Asl(self, rhs)

    def __rshift__(self, rhs):
        return Asr(self, rhs)

    def __and__(self, rhs):
        return BitwiseAnd(self, rhs)

    def __rand__(self, lhs):
        return BitwiseAnd(lhs, self)

    def __or__(self, rhs):
        return BitwiseOr(self, rhs)

    def __ror__(self, lhs):
        return BitwiseOr(lhs, self)

    def __xor__(self, rhs):
        return BitwiseXor(self, rhs)

    def __rxor__(self, lhs):
        return BitwiseXor(lhs, self)

    def __invert__(self):
        return BitwiseNot(self)

    def asfloat(self):
        return CastFloat(self)

    def __lt__(self, rhs):
        return BinaryCondition(self, "<", rhs)

    def __le__(self, rhs):
        return BinaryCondition(self, "<=", rhs)

    def __eq__(self, rhs):
        return BinaryCondition(self, "==", rhs)

    def __ne__(self, rhs):
        return BinaryCondition(self, "!=", rhs)

    def __ge__(self, rhs):
        return BinaryCondition(self, ">=", rhs)

    def __gt__(self, rhs):
        return BinaryCondition(self, ">", rhs)


def get_dtype(value):
    if isinstance(value, (int, np.integer)):
        return int
    if isinstance(value, (float, np.floating)):
        return float
    if isinstance(value, Operand):
        return value.dtype
    # process label as type int.
    if isinstance(value, str) and value[0] == '@':
        return int
    if value is None:
        return type(None)

    return None


class Expression(Operand, ABC):

    @abstractmethod
    def evaluate(self, generator, destination=None):
        pass


class UnaryExpression(Expression):
    def __init__(self, operator, rhs):
        self.operator = operator
        self.rhs = rhs
        self._dtype = self._get_dtype()

    @property
    def dtype(self):
        return self._dtype

    def evaluate(self, generator, destination=None):
        if destination is None:
            destination = generator.get_temp_reg()

        if isinstance(self.rhs, Expression):
            rhs = self.rhs.evaluate(generator)
        else:
            rhs = self.rhs

        self._evaluate(generator, destination, rhs)

        return destination

    @abstractmethod
    def _get_dtype(self):
        pass

    @abstractmethod
    def _evaluate(self, generator, destination, rhs):
        pass

    def __repr__(self):
        return f'{self.operator}{self.rhs}'


class BinaryExpression(Expression):
    def __init__(self, lhs, operator, rhs):
        self.lhs = lhs
        self.operator = operator
        self.rhs = rhs
        self._dtype = self._get_dtype()

    @property
    def dtype(self):
        return self._dtype

    def evaluate(self, generator, destination=None):
        if destination is None:
            destination = generator.get_temp_reg()
        if isinstance(self.lhs, Expression):
            lhs = self.lhs.evaluate(generator)
        else:
            lhs = self.lhs

        if isinstance(self.rhs, Expression):
            rhs = self.rhs.evaluate(generator)
        else:
            rhs = self.rhs

        self._evaluate(generator, destination, lhs, rhs)

        return destination

    @abstractmethod
    def _get_dtype(self):
        pass

    @abstractmethod
    def _evaluate(self, generator, destination, lhs, rhs):
        pass

    def __repr__(self):
        return f'{self.lhs} {self.operator} {self.rhs}'


class Addition(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '+', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.add(lhs, rhs, destination)

    def _get_dtype(self):
        lhs_dtype = get_dtype(self.lhs)
        rhs_dtype = get_dtype(self.rhs)
        if lhs_dtype != rhs_dtype:
            raise Q1TypeError(f'incompatible data types: {self}, '
                              f'{lhs_dtype.__name__} <> {rhs_dtype.__name__}')
        return lhs_dtype


class Subtraction(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '-', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.sub(lhs, rhs, destination)

    def _get_dtype(self):
        lhs_dtype = get_dtype(self.lhs)
        rhs_dtype = get_dtype(self.rhs)
        if lhs_dtype != rhs_dtype:
            raise Q1TypeError(f'incompatible data types: {self}, '
                              f'{lhs_dtype.__name__} <> {rhs_dtype.__name__}')
        return lhs_dtype


class Multiply(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '*', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        if self.dtype == int:
            # TODO @@@ signed or unsigned?
            generator.mul32l(lhs, rhs, destination, signed=True)
        else:
            generator.mul32h(lhs, rhs, destination, signed=True)

    def _get_dtype(self):
        lhs_dtype = get_dtype(self.lhs)
        rhs_dtype = get_dtype(self.rhs)
        if lhs_dtype != rhs_dtype:
            raise Q1TypeError(f'incompatible data types: {self}, '
                              f'{lhs_dtype.__name__} <> {rhs_dtype.__name__}')
        return lhs_dtype


class Lsr(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, 'unsigned >>', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.lsr(lhs, rhs, destination)

    def _get_dtype(self):
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int:
            raise Q1TypeError(f'Shift requires integer number of bits {rhs_dtype.__name__}')
        return get_dtype(self.lhs)


class Asr(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '>>', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.asr(lhs, rhs, destination)

    def _get_dtype(self):
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int:
            raise Q1TypeError(f'Shift requires integer number of bits {self}')
        return get_dtype(self.lhs)


class Asl(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '<<', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.asl(lhs, rhs, destination)

    def _get_dtype(self):
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int:
            raise Q1TypeError(f'Shift requires integer number of bits {self}')
        return get_dtype(self.lhs)


class Bitwise(BinaryExpression, ABC):
    def __init__(self, lhs, operator, rhs):
        super().__init__(lhs, operator, rhs)

    def _get_dtype(self):
        lhs_dtype = get_dtype(self.lhs)
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int or lhs_dtype != int:
            raise Q1TypeError(f'Bitwise operation requires integer values {self}')
        return int


class BitwiseAnd(Bitwise):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '&', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.bits_and(lhs, rhs, destination)


class BitwiseOr(Bitwise):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '|', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.bits_or(lhs, rhs, destination)


class BitwiseXor(Bitwise):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '^', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.bits_xor(lhs, rhs, destination)


class BitwiseNot(UnaryExpression, ABC):
    def __init__(self, rhs):
        super().__init__('~', rhs)

    def _get_dtype(self):
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int:
            raise Q1TypeError(f'Bitwise operation requires integer values {self}')
        return int

    def _evaluate(self, generator, destination, rhs):
        generator.bits_not(rhs, destination)


class CastFloat(UnaryExpression, ABC):
    def __init__(self, rhs):
        super().__init__('float ', rhs)

    def _get_dtype(self):
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int:
            raise Q1TypeError(f'Float cast requires integer value {self}')
        return float

    def _evaluate(self, generator, destination, rhs):
        if id(destination) != id(rhs):
            generator.move(rhs, destination)


class ComparisonOp(Enum):
    EQ = 'z'
    NEQ = 'nz'
    UL = 'b'
    ULE = 'be'
    UG = 'a'
    UGE = 'ae'
    SL = 'l'
    SLE = 'le'
    SG = 'g'
    SGE = 'ge'


class Condition:
    @property
    def comparison_operator(self) -> ComparisonOp:
        return self._comparison_op

    @abstractmethod
    def test(self, generator):
        ...


class BinaryCondition(Expression, Condition):
    """
    TODO doc.
    evaluate: assign result of condition: jxx assign 1 jump @end else: assign 0
    test: set jump condition

    TODO Optimizations for comparison with 0:
        * only evaluate lhs (or rhs) if expression. Use js, jns? lhs < 0, lhs >= 0.
        * if lhs is register use cmp result,0
    """

    def __init__(self, lhs, operator, rhs):
        self.lhs = lhs
        self.operator = operator
        self.rhs = rhs
        lhs_dtype = get_dtype(lhs)
        rhs_dtype = get_dtype(rhs)
        if lhs_dtype != rhs_dtype:
            raise Q1TypeError(f'incompatible data types: {self}, '
                              f'{lhs_dtype.__name__} <> {rhs_dtype.__name__}')
        # TODO add signed int
        self._signed_compare = lhs_dtype == float
        self._dtype = int
        if self._signed_compare:
            operators = {
                '==': ComparisonOp.EQ,
                '!=': ComparisonOp.NEQ,
                '>': ComparisonOp.SG,
                '>=': ComparisonOp.SGE,
                '<': ComparisonOp.SL,
                '<=': ComparisonOp.SLE,
                }
        else:
            operators = {
                '==': ComparisonOp.EQ,
                '!=': ComparisonOp.NEQ,
                '>': ComparisonOp.UG,
                '>=': ComparisonOp.UGE,
                '<': ComparisonOp.UL,
                '<=': ComparisonOp.ULE,
                }
        self._comparison_op = operators[operator]

    @property
    def dtype(self):
        return self._dtype

    def evaluate(self, generator, destination=None):
        if destination is None:
            destination = generator.get_temp_reg()

        self._cmp(generator)

        generator.move(0, destination)
        generator.cmove(self.comparision_operator, 1, destination)

        return destination

    def _cmp(self, generator):
        """
        TODO Optimization for comparison with 0:
            * only evaluate lhs (or rhs) if expression. Use js, jns? lhs < 0, lhs >= 0.
            * if lhs is register use cmp result,0
        """
        if isinstance(self.lhs, Expression):
            lhs = self.lhs.evaluate(generator)
        else:
            lhs = self.lhs

        if isinstance(self.rhs, Expression):
            rhs = self.rhs.evaluate(generator)
        else:
            rhs = self.rhs

        generator.cmp(lhs, rhs)

    def test(self, generator):
        self._cmp(generator)

    @property
    def comparision_operator(self) -> ComparisonOp:
        return self._comparison_op

    def __repr__(self):
        return f'{self.lhs} {self.operator} {self.rhs}'


class ExpressionCondition(Condition):
    def __init__(self, expression: Expression):
        self._expression = expression
        self._comparison_op = ComparisonOp.NEQ

    def test(self, generator):
        self._expression.evaluate(generator)

    def __repr__(self):
        return f'{self._expression}'


class RegisterCondition(Condition):
    def __init__(self, register):
        self._register = register
        self._comparison_op = ComparisonOp.NEQ

    def test(self, generator):
        generator.test(self._register, self._register)

    def __repr__(self):
        return f'{self._register}'
