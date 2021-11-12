from .register import Register

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
        raise Exception(f'Register {r}.{name} not initialized')

    def _set_reg(self, name, value):
        if name not in self._registers:
            self.add_reg(name)

        register = self._registers[name]
        statement = register.assign(value)
        self._builder._add_statement(statement)

    def add_reg(self, name):
        register = Register(name, local=self._local)
        self._registers[name] = register
        super().__setattr__(name, register)
        return register

    def init(self, name, default=0):
        # Note: used for acquire with 'increment'
        register = self.add_reg(name)
        statement = register.assign(default, init_section=True)
        self._builder._add_statement(statement)
        return register
