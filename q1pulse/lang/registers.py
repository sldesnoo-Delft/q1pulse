from .register import Register
from .exceptions import Q1NameError

class Registers:
    def __init__(self, builder, local):
        super().__setattr__('_builder', builder)
        super().__setattr__('_local', local)
        registers = {}
        super().__setattr__('_registers', registers)

    def __getitem__(self, name):
        return self._registers[name]

    def __setitem__(self, name, value):
        self._set_reg(name, value)

    def __setattr__(self, name, value):
        self._set_reg(name, value)

    def __getattr__(self, name):
        r = 'Rs' if self._local else 'R'
        raise Q1NameError(f'Register {r}.{name} not initialized')

    def _set_reg(self, name, value, init_section=False):
        if name not in self._registers:
            self.add_reg(name)

        register = self._registers[name]
        statement = register.assign(value)
        self._builder._add_statement(statement, init_section=init_section)

    def add_reg(self, name):
        register = Register(name, local=self._local)
        self._registers[name] = register
        super().__setattr__(name, register)
        return register

    def init(self, name, default=0):
        # Note: used for acquire with 'increment'
        if name not in self._registers:
            self._set_reg(name, default, init_section=True)
        return self._registers[name]
