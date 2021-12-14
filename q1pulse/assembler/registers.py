from contextlib import contextmanager
from ..lang.exceptions import Q1NameError, Q1MemoryError

class SequencerRegisters:
    def __init__(self, log_func):
        super().__init__()
        self._log = log_func
        self._allocated_regs = {}
        self._free_regs = list(reversed(range(64)))
        # stack with list of registers allcated in scope
        self._scope_regs = []
        self.enter_scope()
        self.allocate_reg('_always_zero_', log=False)
        self._always_zero_initialized = False

    def get_asm_reg(self, name):
        try:
            reg_nr = self._allocated_regs[name]
        except:
            raise Q1NameError(f'Register {name} not defined')
        return f'R{reg_nr}'

    def get_zero_reg(self):
        init_reg = not self._always_zero_initialized
        asm_reg = self.get_asm_reg('_always_zero_')
        if not self._always_zero_initialized:
            self._log(f'{asm_reg}: always 0 register')
            self._always_zero_initialized = True
        return asm_reg, init_reg

    def allocate_reg(self, name, log=True):
        if name in self._allocated_regs:
            self._print_reg_admin()
            raise Q1NameError(f'Register {name} already allocated')

        try:
            reg = self._free_regs.pop()
            self._allocated_regs[name] = reg
            self._scope_regs[-1].append(name)
            if log:
                self._log(f'R{reg}: {name}')
            return self.get_asm_reg(name)
        except IndexError:
            raise Q1MemoryError(f'Cannot allocate register {name}')

    def _release_reg(self, name):
        try:
            reg = self._allocated_regs[name]
        except:
            self._print_reg_admin()
            raise Q1NameError(f'Error in register administration')
        del self._allocated_regs[name]
        self._free_regs.append(reg)

    def enter_scope(self):
        self._scope_regs.append([])

    def exit_scope(self):
        scope_regs = self._scope_regs.pop()
        for name in reversed(scope_regs):
            self._release_reg(name)

    @contextmanager
    def temp_regs(self, n):
        self.enter_scope()
        regs = [self.get_temp_reg(log=False) for i in range(n)]
        self._log(f'temp {regs}')
        yield regs if n > 1 else regs[0]
        self.exit_scope()

    def get_temp_reg(self, log=True):
        try:
            # forge name for register that will be used
            nr = self._free_regs[-1]
            name = f'_R{nr}'
            asm_reg = self.allocate_reg(name, log=False)
            if log:
                self._log(f'temp {asm_reg}')
            return asm_reg
        except IndexError:
            raise Q1MemoryError('Cannot allocate temp register')

    def _print_reg_admin(self):
        # print(f'Free: {self._free_regs}')
        reg_names = {f'R{i}':name for name,i in self._allocated_regs.items()}
        print('Allocated:')
        for r,name in sorted(reg_names.items()):
            print(f'  {r}: {name}')
        indent = 0
        for scope in self._scope_regs:
            indent += 4
            spaces = ' '*indent
            print(f'{spaces}> {scope}')

