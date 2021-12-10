from numbers import Number

from .math_expressions import get_dtype
from .register import Register

class LoopVar(Register):
    def __init__(self, name, loop, **kwargs):
        super().__init__(name, **kwargs)
        self._loop = loop


class Loop:
    def __init__(self, loop_number, n, local=False):
        self._loop_number = loop_number
        self._n = n
        self._loop_reg = LoopVar(f'_cnt{self._loop_number}',
                                 self, local=local, dtype=int)

    @property
    def n(self):
        return self._n

    @property
    def loopvar(self):
        return None

    def __repr__(self):
        return f'repeat({self._n}):'


class RangeLoop(Loop):
    def __init__(self, loop_number, start_or_n, stop=None, step=None):
        if stop is None:
            n = start_or_n
            self._start = 0
            self._stop = n
            self._step = 1
        else:
            self._start = start_or_n
            self._stop = stop
            self._step = 1 if step is None else step
            # loop is end exclusive
            n = (self._stop-1 - self._start) // self._step
            n = max(0, n+1)

        super().__init__(loop_number, n)
        self._reg_name = f'_i{self._loop_number}'
        self._loopvar = LoopVar(self._reg_name, self, dtype=int)

    @property
    def start(self):
        return self._start

    @property
    def stop(self):
        return self._stop

    @property
    def step(self):
        return self._step

    @property
    def n(self):
        return self._n

    @property
    def loopvar(self):
        return self._loopvar

    def __repr__(self):
        return f'loop_range({self.start}, {self.stop}, {self.step}):{self._loopvar}'

class LinspaceLoop(Loop):
    def __init__(self, loop_number, start, stop, n, endpoint=True):
        super().__init__(loop_number, n)
        if max(start,stop) > 1.0 or min(start,stop) < -1.0:
            raise Exception('value out of range [-1.0, 1.0]')
        self._start = start
        self._stop = stop
        self._endpoint = endpoint
        step_divisor = (n-1) if endpoint else n
        self._increment = (stop - start)/step_divisor
        self._reg_name = f'_f{self._loop_number}'
        self._loopvar = LoopVar(self._reg_name, self, dtype=float)

    @property
    def start(self):
        return self._start

    @property
    def stop(self):
        return self._stop

    @property
    def endpoint(self):
        return self._endpoint

    @property
    def increment(self):
        return self._increment

    @property
    def loopvar(self):
        return self._loopvar

    def __repr__(self):
        endpoint = ', endpoint=False' if not self.endpoint else ''
        return f'loop_linspace({self.start}, {self.stop}, {self.n}{endpoint}):{self.loopvar}'

class ArrayLoop(Loop):
    def __init__(self, loop_number, values):
        super().__init__(loop_number, len(values))
        self.values = values
        dtype = get_dtype(values[0])
        for value in values[1:]:
            if get_dtype(values[0]) != dtype:
                raise Exception('Array values must all be same type')
        if dtype == float:
            literal_values = [value for value in values if isinstance(value, Number)]
            if max(literal_values) > 1.0 or min(literal_values) < -1.0:
                raise Exception('value out of range [-1.0, 1.0]')

        self._reg_name = f'_f{self._loop_number}'
        self._loopvar = LoopVar(self._reg_name, self, dtype=dtype)
        self._table_label = f'_table{self._loop_number}'
        self._data_ptr = Register(f'_ptr{self._loop_number}')

    @property
    def loopvar(self):
        return self._loopvar

    def __repr__(self):
        return f'loop_array({self.values}):{self.loopvar}'
