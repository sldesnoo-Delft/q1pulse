from abc import abstractmethod
from .builderbase import Expression, get_dtype

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

    def __repr__(self):
        return f'{self.lhs} {self.operator} {self.rhs}'

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

class Asr(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '>>', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.asr(lhs, rhs, destination)

    def _get_dtype(self):
        return get_dtype(self.lhs)

class Asl(BinaryExpression):
    def __init__(self, lhs, rhs):
        super().__init__(lhs, '<<', rhs)

    def _evaluate(self, generator, destination, lhs, rhs):
        generator.asl(lhs, rhs, destination)

    def _get_dtype(self):
        return get_dtype(self.lhs)
