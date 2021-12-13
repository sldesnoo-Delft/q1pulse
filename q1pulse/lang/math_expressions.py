from abc import abstractmethod, ABC

import numpy as np

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

def get_dtype(value):
    if isinstance(value, (int, np.integer)):
        return int
    if isinstance(value, (float, np.float)):
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
            raise Exception(f'incompatible data types: {self}, {lhs_dtype.__name__} <> {rhs_dtype.__name__}')
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
            raise Exception('incompatible data types: {self}')
        return lhs_dtype

class Lsr(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, 'unsigned >>', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.lsr(lhs, rhs, destination)

    def _get_dtype(self):
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int:
            raise Exception(f'Shift requires integer number of bits {rhs_dtype.__name__}')
        return get_dtype(self.lhs)

class Asr(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '>>', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.asr(lhs, rhs, destination)

    def _get_dtype(self):
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int:
            raise Exception(f'Shift requires integer number of bits {rhs_dtype.__name__}')
        return get_dtype(self.lhs)

class Asl(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '<<', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.asl(lhs, rhs, destination)

    def _get_dtype(self):
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int:
            raise Exception(f'Shift requires integer number of bits {rhs_dtype.__name__}')
        return get_dtype(self.lhs)


class Bitwise(BinaryExpression, ABC):
    def __init__(self, lhs, operator, rhs):
        super().__init__(lhs, operator, rhs)

    def _get_dtype(self):
        lhs_dtype = get_dtype(self.lhs)
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int or lhs_dtype != int:
            raise Exception(f'Bitwise operation requires integer values')
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
            raise Exception(f'Bitwise operation requires integer values')
        return int

    def _evaluate(self, generator, destination, rhs):
        generator.bits_not(rhs, destination)

class CastFloat(UnaryExpression, ABC):
    def __init__(self, rhs):
        super().__init__('float ', rhs)

    def _get_dtype(self):
        rhs_dtype = get_dtype(self.rhs)
        if rhs_dtype != int:
            raise Exception(f'Float cast expects integer value')
        return float

    def _evaluate(self, generator, destination, rhs):
        if destination != rhs:
            generator.move(rhs, destination)

