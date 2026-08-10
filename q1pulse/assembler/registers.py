from contextlib import contextmanager
from ..lang.exceptions import Q1NameError, Q1MemoryError


class SequencerRegisters:
    stack_size = 30
    static_size = 20

    def __init__(self, log_func):
        super().__init__()
        self._log = log_func
        self._allocated_regs = {}
        # stack for registers allocated in scope
        self._stack_ptr = 0
        self._n_static = 0
        self._static_regs = []
        self._scope = []
        self.enter_scope()

    def get_asm_reg(self, name):
        try:
            return self._allocated_regs[name]
        except KeyError:
            raise Q1NameError(f"Register {name} not defined") from None

    def allocate_reg(self, name, log: bool = True, static: bool = False):
        if name in self._allocated_regs:
            self._print_reg_admin()
            raise Q1NameError(f"Register {name} already allocated")
        try:
            if static:
                asm_reg = self._allocate_static_reg(name)
            else:
                asm_reg = self._allocate_stack_reg(name)
            self._allocated_regs[name] = asm_reg
            if log and self._log is not None:
                self._log(f"{asm_reg}: {name}")
            return asm_reg
        except IndexError:
            raise Q1MemoryError(f"Cannot allocate register {name}") from None

    def enter_scope(self):
        self._scope.append((self._stack_ptr, {})) # @@@@ replace by list

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
            self._log(f"temp {regs}")
        yield regs if n > 1 else regs[0]
        self.exit_scope()

    def _allocate_stack_reg(self, name=None):
        reg_nr = self._stack_ptr
        self._stack_ptr += 1
        if self._stack_ptr >= SequencerRegisters.stack_size:
            raise Q1MemoryError("Stack overflow")
        reg_name = f"R{reg_nr}"
        if name:
            self._scope[-1][1][name] = reg_name
        return reg_name

    def _allocate_static_reg(self, name):
        reg_nr = self._n_static + SequencerRegisters.stack_size
        self._n_static += 1
        if self._n_static >= SequencerRegisters.static_size:
            raise Q1MemoryError("Out of static register memory")
        self._static_regs.append(name)
        reg_name = f"R{reg_nr}"
        return reg_name

    def get_temp_reg(self, log=True):
        asm_reg = self._allocate_stack_reg()
        if log and self._log:
            self._log(f"temp {asm_reg}")
        return asm_reg

    def get_scope_regs(self):
        res = {}
        for scope in reversed(self._scope):
            for name in scope[1]:
                res[name] = self.get_asm_reg(name)
        return res

    def get_static_regs(self):
        res = {}
        for name in self._static_regs:
            res[name] = self.get_asm_reg(name)
        return res

    def _print_reg_admin(self):
        # print(f"Free: {self._free_regs}")
        reg_names = {f"R{i}": name for name, i in self._allocated_regs.items()}
        print("Allocated:")
        for r, name in sorted(reg_names.items()):
            print(f"  {r}: {name}")
        indent = 0
        for scope in self._scope:
            indent += 4
            spaces = " "*indent
            print(f"{spaces}> {scope}")
