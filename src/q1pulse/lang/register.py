from .register_statements import RegisterAssignment, AllocateVariable
from .math_expressions import Operand


class Register(Operand):
    def __init__(self, name, local=False, dtype=None):
        self.short_name = name
        self.local = local
        self._dtype = dtype
        self.full_name = f'Rs.{name}' if local else f'R.{name}'
        self._allocated = False

    @property
    def dtype(self):
        return self._dtype

    @property
    def name(self):
        return self.full_name

    def assign(self, value_or_expression, allocate=False):
        allocate = not self._allocated or allocate
        if not self._allocated:
            self._allocated = True
        return RegisterAssignment(self, value_or_expression, allocate=allocate)

    def allocate_variable(self, dtype):
        self._allocated = True
        self._dtype = dtype
        return AllocateVariable(self)

    def __repr__(self):
        return self.full_name
