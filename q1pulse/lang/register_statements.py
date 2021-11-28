from .base import Statement
from .math_expressions import Expression, get_dtype

class RegisterAssignment(Statement):
    def __init__(self, destination, value_or_expression, allocate=False):
        self.destination = destination
        self.value_or_expression = value_or_expression
        self.allocate = allocate
        if allocate:
            destination._dtype = get_dtype(value_or_expression)

    def __repr__(self):
        dtype = self.destination.dtype.__name__
        return f'{self.destination}:{dtype} = {self.value_or_expression}'

    def write_instruction(self, generator):
        if self.allocate:
            generator.allocate_reg(self.destination.name)

        if isinstance(self.value_or_expression, Expression):
            with generator.scope():
                expression = self.value_or_expression
                expression.evaluate(generator, self.destination)
        else:
            generator.move(self.value_or_expression, self.destination)



