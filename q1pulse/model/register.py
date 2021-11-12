from .builderbase import Typed
from .register_statements import RegisterAssignment
from .math_expressions import Addition, Subtraction, Asl, Asr

class Register(Typed):
    def __init__(self, name, local=False):
        self.name = f'Rs.{name}' if local else f'R.{name}'
        self._initialized = False
        self._dtype = None

    @property
    def dtype(self):
        return self._dtype

    def assign(self, value_or_expression, init_section=False):
        allocate = not self._initialized
        if not self._initialized:
            self._initialized = True
        statement = RegisterAssignment(self, value_or_expression,
                                       allocate=allocate, init_section=init_section)
        return statement

    def __repr__(self):
        return self.name

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
