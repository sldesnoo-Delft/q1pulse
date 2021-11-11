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
        register.assign(value)

    def add_reg(self, name): # @@@ move value to Register.__init__, but conflict in Loops...
        register = Register(name, self._builder, local=self._local)
        self._registers[name] = register
        super().__setattr__(name, register)
        return register

    def init(self, name, default=0): # @@@ used for acquire 'increment'
        register = self.add_reg(name)
        register.assign(default, init_section=True)
        return register

#    def _assign(self, register, value_or_expression, init=False):
##        if value_or_expression == self:
##            return
#
#        # if is_float is None: self.is_float = is_float(value_or_expression)
#        # else: assert is_float(value_or_expression) == self.is_float
#        if not self._initialized:
#            self._dtype = get_dtype(value_or_expression)
#            self._builder._add_statement(RegisterAllocation(self))
#            self._initialized = True
#        statement = RegisterAssignment(self, value_or_expression, init_section=init)
#        self._builder._add_statement(statement)
