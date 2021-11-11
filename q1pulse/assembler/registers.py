from contextlib import contextmanager

class SequencerRegisters:
    def __init__(self, log_func):
        super().__init__()
        self._log = log_func
        self._allocated_regs = {}
        self._free_regs = list(reversed(range(64)))
        # stack with list of registers allcated in scope
        self._scope_regs = []
        self.enter_scope()

    def get_asm_reg(self, name):
        try:
            reg_nr = self._allocated_regs[name]
        except:
            raise Exception(f'Register {name} not defined')
        return f'R{reg_nr}'

    def get_dummy_reg(self):
        name = '_empty_dummy_'
        if name not in self._allocated_regs:
            self.allocate_reg(name, global_scope=True)
            init_reg = True
        else:
            init_reg = False
        asm_reg = self.get_asm_reg(name)
        return asm_reg, init_reg

    def allocate_reg(self, name, global_scope=False):
        if name in self._allocated_regs:
            self._print_reg_admin()
            raise Exception(f'Register {name} already allocated')

        reg = self._free_regs.pop()
        self._allocated_regs[name] = reg
        if not global_scope:
            self._scope_regs[-1].append(name)
        self._log(f'R{reg}: {name}')
        return self.get_asm_reg(name)

    def _release_reg(self, name):
        try:
            reg = self._allocated_regs[name]
        except:
            self._print_reg_admin()
            raise Exception(f'Error in register administration')
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
        regs = [self.get_temp_reg() for i in range(n)]
#        print(f'temp regs: {regs}')
        yield regs if n > 1 else regs[0]
        self.exit_scope()

    def get_temp_reg(self):
        # forge name for register that will be used
        nr = self._free_regs[-1]
        name = f'_R{nr}'
        return self.allocate_reg(name)

    def _print_reg_admin(self):
#        print(f'Free: {self._free_regs}')
        reg_names = {f'R{i}':name for name,i in self._allocated_regs.items()}
        print('Allocated:')
        for r,name in sorted(reg_names.items()):
            print(f'  {r}: {name}')
        indent = 0
        for scope in self._scope_regs:
            indent += 4
            spaces = ' '*indent
            print(f'{spaces}> {scope}')

