from .base import Statement

class LogStatement(Statement):
    def __init__(self, msg, register, time=False):
        self.msg = msg
        self.register = register
        self.options = ''
        if time:
            self.options += 'T'
        if register is not None:
            self.options += 'R'
            if register.dtype == float:
                self.options += 'F'

    def write_instruction(self, generator):
        generator.sim_log(self.msg, self.register, self.options)

    def __repr__(self):
        return f'log "{self.msg}",{self.register},{self.options}'
