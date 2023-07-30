from contextlib import contextmanager
from ..lang.exceptions import Q1NameError, Q1MemoryError

class SequencerRegisters:
    stack_size = 32

    def __init__(self, log_func):
        super().__init__()
        self._log = log_func
        self._allocated_regs = {}
        # stack for registers allcated in scope
        self._stack_ptr = 0
        self._scope = []
        self.enter_scope()

    def get_asm_reg(self, name):
        try:
            return self._allocated_regs[name]
        except KeyError:
            raise Q1NameError(f'Register {name} not defined')

    def allocate_reg(self, name, log=True):
        if name in self._allocated_regs:
            self._print_reg_admin()
            raise Q1NameError(f'Register {name} already allocated')
        try:
            asm_reg = self._allocate_stack_reg(name)
            self._allocated_regs[name] = asm_reg
            if log and self._log is not None:
                self._log(f'{asm_reg}: {name}')
            return asm_reg
        except IndexError:
            raise Q1MemoryError(f'Cannot allocate register {name}')

    def enter_scope(self):
        self._scope.append((self._stack_ptr, {}))

    def exit_scope(self):
        ptr, named = self._scope.pop()
        self._stack_ptr = ptr
        for reg_name in named:
            del self._allocated_regs[reg_name]

    @contextmanager
    def temp_regs(self, n):
        self.enter_scope()
        regs = [self.get_temp_reg(log=False) for i in range(n)]
        if self._log is not None:
            self._log(f'temp {regs}')
        yield regs if n > 1 else regs[0]
        self.exit_scope()

    def _allocate_stack_reg(self, name=None):
        reg_nr = self._stack_ptr
        self._stack_ptr += 1
        if self._stack_ptr >= SequencerRegisters.stack_size:
            raise Q1MemoryError('Stack overflow')
        reg_name = f'R{reg_nr}'
        if name:
            self._scope[-1][1][name] = reg_name
        return reg_name

    def get_temp_reg(self, log=True):
        asm_reg = self._allocate_stack_reg()
        if log and self._log:
            self._log(f'temp {asm_reg}')
        return asm_reg

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

