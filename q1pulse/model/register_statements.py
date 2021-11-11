from .builderbase import Statement, Expression
from .builderbase import get_dtype


class RegisterAssignment(Statement):
    def __init__(self, destination, value_or_expression,
                 allocate=False, init_section=False):
        self.destination = destination
        self.value_or_expression = value_or_expression
        self.init_section = init_section
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
            generator.move(self.value_or_expression, self.destination, self.init_section)


class RegisterBinOp(Statement):
    def __init__(self, destination, lhs, rhs):
        self.destination = destination
        self.lhs = lhs
        self.rhs = rhs


class RegisterAdd(RegisterBinOp):
    def __repr__(self):
        return f'{self.destination} = {self.lhs} + {self.rhs}'

    def write_instruction(self, generator):
        generator.add(self.lhs, self.rhs, self.destination)

class RegisterSub(RegisterBinOp):
    def __repr__(self):
        return f'{self.destination} = {self.lhs} - {self.rhs}'

    def write_instruction(self, generator):
        generator.sub(self.lhs, self.rhs, self.destination)


class RegisterAsr(RegisterBinOp):
    def __repr__(self):
        return f'{self.destination} = {self.lhs} >> {self.rhs}'

    def write_instruction(self, generator):
        generator.asr(self.lhs, self.rhs, self.destination)


class RegisterAsl(RegisterBinOp):
    def __repr__(self):
        return f'{self.destination} = {self.lhs} << {self.rhs}'

    def write_instruction(self, generator):
        generator.asl(self.lhs, self.rhs, self.destination)


