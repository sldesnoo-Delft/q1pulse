from .control import ControlBuilder
from .timed_statements import AcquireStatement


class ReadoutBuilder(ControlBuilder):
    def __init__(self, name, enabled_paths):
        super().__init__(name, enabled_paths)

    def acquire(self, section, bin_index, t_offset=0):
        t1 = self.current_time + t_offset
        if bin_index == 'increment':
            reg_name = f'_bin{section}'
            bin_reg = self.Rs.init(reg_name)
            self._add_statement(AcquireStatement(t1, section, bin_reg))
            self.Rs[reg_name] += 1
        else:
            self._add_statement(AcquireStatement(t1, section, bin_index))

    def reset_bin_counter(self, section):
        reg_name = f'_bin{section}'
        self.Rs[reg_name] = 0
