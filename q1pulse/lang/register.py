from .register_statements import RegisterAssignment
from .math_expressions import Operand

class Register(Operand):
    def __init__(self, name, local=False, dtype=None):
        self.name = f'Rs.{name}' if local else f'R.{name}'
        self._initialized = False
        self._dtype = dtype

    @property
    def dtype(self):
        return self._dtype

    def assign(self, value_or_expression, allocate=False):
        allocate = not self._initialized or allocate
        if not self._initialized:
            self._initialized = True
        return RegisterAssignment(self, value_or_expression, allocate=allocate)

    def __repr__(self):
        return self.name
