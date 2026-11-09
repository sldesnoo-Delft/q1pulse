from .exceptions import Q1NameError
from .register import Register
from .program_variables import Variable


class Registers:
    def __init__(self, builder, local):
        # Assign fields using super to avoid complications with self.__setattr__
        super().__setattr__("_builder", builder)
        super().__setattr__("_local", local)
        registers = {}
        super().__setattr__("_registers", registers)
        variables = {}
        super().__setattr__("_variables", variables)

    def __getitem__(self, name):
        return self._registers[name]

    def __setitem__(self, name, value):
        self._set_reg(name, value)

    def __setattr__(self, name, value):
        self._set_reg(name, value)

    def __getattr__(self, name):
        r = "Rs" if self._local else "R"
        raise Q1NameError(f"Register {r}.{name} not initialized")

    def _set_reg(self, name, value, init_section=False):
        if name not in self._registers:
            self.add_reg(name)

        register = self._registers[name]

        if isinstance(value, Variable):
            if name in self._variables:
                raise Q1NameError(f"Variable {name} is already declared")
            variable = value
            self._variables[register.short_name] = variable
            statement = register.allocate_variable(variable.dtype)
            self._builder._add_statement(statement, init_section=True)

            if variable.initial_value is not None:
                if variable.init_scope in ["start", "repeat_loop"]:
                    statement = register.assign(variable.initial_value, allocate=False)
                    set_before_repeat = variable.init_scope == "start"
                    self._builder._add_statement(statement, init_section=set_before_repeat)
        else:
            statement = register.assign(value)
            self._builder._add_statement(statement, init_section=init_section)

    def add_reg(self, name):
        register = Register(name, local=self._local)
        self._registers[name] = register
        super().__setattr__(name, register)
        return register

    def init(self, name, default=0):
        # Note: used for acquire with "increment"
        if name not in self._registers:
            self._set_reg(name, default, init_section=True)
        return self._registers[name]

    @property
    def variables(self):
        return self._variables.copy()
